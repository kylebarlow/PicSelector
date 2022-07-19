import os
import datetime
import sys
import io
import time
import hashlib
import multiprocessing
import tempfile
import argparse
from pprint import pprint

import filetype
import watchdog
import watchdog.events
import watchdog.observers
import PIL
import PIL.ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
import imagehash
# import face_recognition
from dateutil import parser as dateutil_parser
import ffmpeg
import numpy as np
import pandas as pd

from sshtunnel import SSHTunnelForwarder
import psycopg2
import config

from timezonefinder import TimezoneFinder
import pytz

import boto3
import botocore
import botocore.exceptions


def process_media_file(event):
    fpath = event.src_path

    if filetype.helpers.is_image(fpath):
        metadata = process_image(fpath)
    elif filetype.helpers.is_video(fpath):
        metadata = process_video(fpath)
    metadata['fpath'] = os.path.abspath(fpath)
    return metadata


def generate_thumbnail(in_filename, out_filename, time, width):
    try:
        (
            ffmpeg
            .input(in_filename, ss=time)
            .filter('scale', width, -1)
            .output(out_filename, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print(e.stderr.decode(), file=sys.stderr)
        raise


def make_ss_time(time_in_s):
    return str(datetime.timedelta(seconds=time_in_s))


def process_video(fpath, max_thumbnail_height=400, max_thumbnail_samples=1000):
    info = find_probe_info(ffmpeg.probe(fpath), desired_keys=['duration', 'location', 'creation_time', 'height', 'width'])
    # pprint(ffmpeg.probe(fpath))

    with open(fpath, "rb") as f:
        file_hash = hashlib.sha256()
        while chunk := f.read(64*16):
            file_hash.update(chunk)
    sha_hash = file_hash.digest()

    date_time = None
    zulu_time = False
    original_tzinfo = None
    if 'creation_time' in info:
        date_time = dateutil_parser.parse((info['creation_time'][0]))
        if isinstance(info['creation_time'][0], str) and len(info['creation_time'][0]) > 0 and info['creation_time'][0][-1].upper() == 'Z':
            zulu_time = True
            original_tzinfo = date_time.tzinfo

    duration = None
    if 'duration' in info:
        duration = float(info['duration'][0])

    height = None
    if 'height' in info:
        height = int(info['height'][0])

    width = None
    if 'width' in info:
        width = int(info['width'][0])

    lat = None
    lon = None
    if 'location' in info:
        try:
            loc_str = info['location'][0]
            if loc_str.endswith('/'):
                loc_str = loc_str[:-1]
            if loc_str[0] == '+' and '-' in loc_str:
                lat = float(loc_str.split('-')[0][1:])
                lon = float(loc_str.split('-')[1])
        except Exception:
            pass

    if date_time and lat and lon and zulu_time:
        tf = TimezoneFinder()
        tz = pytz.timezone(tf.timezone_at(lng=lon, lat=lat))
        date_time = date_time.astimezone(tz).replace(tzinfo=original_tzinfo)
        print('Adjusted time', date_time)

    filesize = os.path.getsize(fpath)

    thumbnail_paths = []
    if duration is not None:
        if duration <= 10:
            thumbnail_samples = range(0, max(int(duration), 1))
        elif duration <= 60 or duration < max_thumbnail_samples:
            thumbnail_samples = range(0, int(duration))
        else:
            thumbnail_samples = np.linspace(0, duration, num=max_thumbnail_samples).astype(int)

        # print(fpath, duration)
        for s in thumbnail_samples:
            s = int(s)
            ss = make_ss_time(s)
            with tempfile.NamedTemporaryFile('wb', suffix='_vthumb.jpg', delete=False) as f:
                thumbnail_path = os.path.abspath(f.name)
            try:
                generate_thumbnail(fpath, thumbnail_path, ss, max_thumbnail_height)
                thumbnail_paths.append(thumbnail_path)
            except Exception:
                pass

    best_thumbnail_path = None
    if len(thumbnail_paths) > 0:
        ahashes = []
        for thumbnail_path in thumbnail_paths:
            image = PIL.Image.open(thumbnail_path)
            ahashes.append(imagehash.average_hash(image))
        
        distances = []
        for i, ahash_i in enumerate(ahashes):
            distances.append((np.mean([ahash_i-ahash_j for ahash_j in ahashes]), i))
        distances.sort()
        mean_i = distances[0][1]

        best_thumbnail_path = thumbnail_paths[mean_i]
        for i, thumbnail_path in enumerate(thumbnail_paths):
            if i != mean_i:
                os.remove(thumbnail_path)

    thumbnail_width = None
    thumbnail_height = None
    thumbnail_size = None
    if best_thumbnail_path is not None:
        image = PIL.Image.open(best_thumbnail_path)
        thumbnail_width = image.width
        thumbnail_height = image.height
        thumbnail_size = os.path.getsize(best_thumbnail_path)

    return {
        'lat': lat,
        'lon': lon,
        'height': height,
        'width': width,
        'size': filesize,
        'sha256_hash': sha_hash,
        'creation_time': date_time,
        'media_type': 'video',
        'thumbnail': {
            'thumbnail_path': best_thumbnail_path,
            'thumbnail_width': thumbnail_width,
            'thumbnail_height': thumbnail_height,
            'thumbnail_size': thumbnail_size,
        },
        'video_only': {
            'duration': duration,
        }
    }


def find_probe_info(d, desired_keys=[]):
    found_info = {desired_key: [] for desired_key in desired_keys}
    for k, v in d.items():
        if isinstance(v, dict):
            for desired_key, l in find_probe_info(v, desired_keys=desired_keys).items():
                found_info[desired_key].extend(l)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    for desired_key, l in find_probe_info(x, desired_keys=desired_keys).items():
                        found_info[desired_key].extend(l)
        else:
            for desired_key in desired_keys:
                if k == desired_key:
                    found_info[desired_key].append(v)

    # Remove duplicates by converting to set
    found_info = {k: set(v) for k, v in found_info.items() if len(v) > 0}
    found_info = {k: list(v) for k, v in found_info.items()}
    return found_info


def get_decimal_from_dms(dms, ref):
    try:
        degrees = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1] / 60.0
        seconds = dms[2][0] / dms[2][1] / 3600.0
    except TypeError:
        degrees = dms[0]
        minutes = dms[1] / 60.0
        seconds = dms[2] / 3600.0

    if ref in ['S', 'W']:
        degrees = -degrees
        minutes = -minutes
        seconds = -seconds

    return degrees + minutes + seconds


def process_image(fpath, max_thumbnail_height=400, run_hashing=True):
    with open(fpath, 'rb') as f:
        fdata = f.read()
    sha_hash = hashlib.sha256(fdata).digest()
    image = PIL.Image.open(io.BytesIO(fdata))
    hashes = {}
    hashes['average'] = ' ' * 16
    hashes['perceptual'] = ' ' * 16
    hashes['difference'] = ' ' * 16
    if run_hashing:
        try:
            hashes['average'] = str(imagehash.average_hash(image))
        except Exception:
            pass
        try:
            hashes['perceptual'] = str(imagehash.phash(image))
        except Exception:
            pass
        try:
            hashes['difference'] = str(imagehash.dhash(image))
        except Exception:
            pass

    exif_data = image.getexif()
    exif_dict = {}
    for tag_id, data in exif_data.items():
        # get the tag name, instead of human unreadable tag id
        tag = PIL.ExifTags.TAGS.get(tag_id, tag_id)
        if tag == 'GPSInfo':
            continue
        try:
            if isinstance(data, bytes):
                data = data.decode()
            exif_dict[tag] = data
        except Exception:
            pass

    # This seems dumb, but image._getexif() returns different information than image.getexif()
    raw_exif_data = {}
    if image._getexif() is not None:
        for tag, value in image._getexif().items():
            try:
                raw_exif_data[TAGS.get(tag, tag)] = value
            except Exception:
                pass

    geotags = {}
    if 'GPSInfo' in raw_exif_data:
        for tag, value in raw_exif_data['GPSInfo'].items():
            try:
                geotags[GPSTAGS.get(tag, tag)] = value
            except Exception:
                pass

    lat = None
    lon = None
    try:
        lat = get_decimal_from_dms(geotags['GPSLatitude'], geotags['GPSLatitudeRef'])
    except KeyError:
        pass
    try:
        lon = get_decimal_from_dms(geotags['GPSLongitude'], geotags['GPSLongitudeRef'])    
    except KeyError:
        pass
    if lat == 0 and lon == 0:
        lat = None
        lon = None

    date_time = set([value for key, value in exif_dict.items() if isinstance(key, str) and key.startswith('DateTime')])
    if len(date_time) == 0:
        date_time = None
    else:
        date_time = datetime.datetime.strptime(list(date_time)[0], '%Y:%m:%d %H:%M:%S')

    if date_time is None and 'GPSDateStamp' in geotags and 'GPSTimeStamp' in geotags:
        try:
            year, month, day = geotags['GPSDateStamp'].split(':')
            date_time = datetime.datetime(year=year, month=month, day=day, hour=geotags['GPSTimeStamp'][0], minute=geotags['GPSTimeStamp'][1], second=geotags['GPSTimeStamp'][2])
        except Exception:
            pass
    if date_time is None and 'GPSDateStamp' in geotags:
        try:
            year, month, day = geotags['GPSDateStamp'].split(':')
            date_time = datetime.datetime(year=year, month=month, day=day)
        except Exception:
            pass
    if date_time is None:
        try:
            extension_length = len(fpath.split('.')[-1]) + 1
            date_time = datetime.datetime.strptime(os.path.basename(fpath)[:-extension_length], "%Y-%m-%d %H.%M.%S")
        except Exception:
            pass
    if date_time is None:
        try:
            extension_length = len(fpath.split('.')[-1]) + 1
            date_time = dateutil_parser.parse(os.path.basename(fpath)[:-extension_length])
        except Exception:
            pass

    max_size = (min(max_thumbnail_height*3, image.height), max_thumbnail_height)
    thumbnail = PIL.ImageOps.exif_transpose(image).copy()
    width = thumbnail.width
    height = thumbnail.height
    thumbnail.thumbnail(max_size)
    with tempfile.NamedTemporaryFile('wb', suffix='_ithumb.jpg', delete=False) as f:
        thumbnail_path = os.path.abspath(f.name)
        try:
            thumbnail.save(f, format='JPEG')
        except OSError:
            thumbnail.convert('RGB').save(f, format='JPEG')

    # fr_image = face_recognition.load_image_file(io.BytesIO(fdata))
    # face_locations = face_recognition.face_locations(fr_image)
    # face_encodings = face_recognition.face_encodings(fr_image, num_jitters=3)
    
    return {
        'lat': lat,
        'lon': lon,
        'height': height,
        'width': width,
        'size': sys.getsizeof(fdata),
        'sha256_hash': sha_hash,
        'creation_time': date_time,
        'media_type': 'image',
        'thumbnail': {
            'thumbnail_path': thumbnail_path,
            'thumbnail_width': thumbnail.width,
            'thumbnail_height': thumbnail.height,
            'thumbnail_size': os.path.getsize(thumbnail_path),
        },
        'image_only': {
            'hashes': hashes,
        }
    }


class DirectoryMonitor():
    def __init__(
        self, root_dir,
        subdirs_only=[],
        start_date=None,
        remove_after_upload=False,
        check_existing_hashes=False,
        add_existing_files=True, monitor_new=True, max_file_queue_size=100, 
        num_processing_threads=4, processing_niceness=10, max_metadata_queue_size=5000, max_s3_queue_size=1000, num_s3_threads=1,
    ):
        assert(os.path.isdir(root_dir))
        self.remove_after_upload = remove_after_upload
        self.root_dir = os.path.abspath(root_dir)
        self.start_date = start_date
        self.subdirs_only = subdirs_only
        if len(subdirs_only) > 0:
            self.subdirs_only = [os.path.abspath(s) for s in subdirs_only if os.path.isdir(s)]
        self.add_existing_files = add_existing_files
        self.progress_queue = multiprocessing.Queue()
        self.queue = multiprocessing.Queue(maxsize=max_file_queue_size)
        self.watchdog_queue = multiprocessing.Queue()
        self.metadata_queue = multiprocessing.Queue(maxsize=max_metadata_queue_size)
        self.s3_queue = multiprocessing.Queue(maxsize=max_s3_queue_size)
        self.path_queue = multiprocessing.Queue()
        self.num_processing_threads = num_processing_threads
        if monitor_new:
            self.initialize_watchdogs()
            self.queue_combiner = multiprocessing.Process(target=combine_queues, args=(self.queue, self.watchdog_queue))
            self.queue_combiner.start()
        else:
            assert(add_existing_files)

        if check_existing_hashes:
            existing_hashes = get_existing_hashes()
        else:
            existing_hashes = set()
        # print('Existing hashes')
        # print(list(existing_hashes)[:5])
        # sys.exit()

        self.initial_walkers = []
        if self.add_existing_files:
            if len(self.subdirs_only) > 0:
                for subdir in self.subdirs_only:
                    self.initial_walkers.append(multiprocessing.Process(target=walk_dir, args=(subdir, self.queue, existing_hashes, remove_after_upload)))
            else:
                self.initial_walkers.append(multiprocessing.Process(target=walk_dir, args=(self.root_dir, self.queue, existing_hashes, remove_after_upload)))
            for iw in self.initial_walkers:
                iw.start()

        self.media_process_pool = multiprocessing.Pool(
            processes=self.num_processing_threads,
            initializer=media_processor_worker,
            initargs=(self.queue, self.metadata_queue, processing_niceness, self.root_dir, self.start_date)
        )

        self.metadata_worker = multiprocessing.Process(target=metadata_processor_worker, args=(self.metadata_queue, self.s3_queue, self.path_queue))
        self.metadata_worker.start()

        self.path_worker = multiprocessing.Process(target=path_queue_worker, args=(self.path_queue, self.remove_after_upload))
        self.path_worker.start()

        self.num_s3_threads = num_s3_threads
        self.s3_upload_pool = multiprocessing.Pool(
            processes=self.num_s3_threads,
            initializer=s3_upload_worker,
            initargs=(self.s3_queue, self.path_queue)
        )

        if not monitor_new:
            self.exit_when_initial_processing_done()

    def exit_when_initial_processing_done(self):
        for iw in self.initial_walkers:
            iw.join()
        number_times_queue_0 = 0
        while number_times_queue_0 < 5:
            time.sleep(0.2)
            if self.queue.qsize() == 0:
                number_times_queue_0 += 1
            else:
                number_times_queue_0 = 0
        for i in range(self.num_processing_threads):
            self.queue.put(None)
        self.media_process_pool.close()
        self.media_process_pool.join()
        time.sleep(0.4)
        self.metadata_queue.put(None)
        self.metadata_worker.join()
        time.sleep(0.4)
        for i in range(self.num_s3_threads):
            self.s3_queue.put(None)
        self.s3_upload_pool.close()
        self.s3_upload_pool.join()
        self.path_queue.put(None)
        self.path_worker.join()

    def initialize_watchdogs(self):
        self.event_handlers = []
        self.observers = []
        if len(self.subdirs_only) == 0:
            event_handler = FileWatchdog(self.watchdog_queue)
            observer = watchdog.observers.Observer()
            root_dir = self.root_dir
            observer.schedule(event_handler, root_dir, recursive=True)
            observer.start()
            self.event_handlers.append(event_handler)
            self.observers.append(observer)
        else:
            for subdir in self.subdirs_only:
                root_dir = subdir
                event_handler = FileWatchdog(self.watchdog_queue)
                observer = watchdog.observers.Observer()
                observer.schedule(event_handler, root_dir, recursive=True)
                observer.start()
                self.event_handlers.append(event_handler)
                self.observers.append(observer)


class FileWatchdog(watchdog.events.PatternMatchingEventHandler):
    def __init__(self, queue, **kwargs):
        super().__init__(**kwargs)
        self.queue = queue

    def process(self, event):
        if os.path.basename(event.src_path)[0] == '.':
            pass
        elif path_is_image_or_video(event.src_path):
            self.queue.put(event)
        # return super().process(event)

    def on_created(self, event):
        self.process(event)
        # return super().process(event)


def media_processor_worker(file_queue, metadata_queue, niceness, root_dir, start_date):
    os.nice(niceness)
    while True:
        event = file_queue.get()
        if event is None:
            break
        if start_date is not None:
            fpath = event.src_path
            # First try filename
            fname = os.path.splitext(os.path.basename(fpath))[0]
            try:
                file_creation_time = datetime.datetime.strptime(fname, '%Y-%m-%d %H.%M.%S')
            except ValueError:
                # Fallback to file creation time
                file_creation_time = datetime.datetime.fromtimestamp(os.path.getctime(fpath))
            if file_creation_time < start_date:
                continue

        metadata = process_media_file(event)
        metadata['fpath'] = os.path.abspath(metadata['fpath'])
        metadata['fpath_relative'] = os.path.relpath(metadata['fpath'], root_dir)
        metadata_queue.put(metadata)


def get_existing_hashes():
    with DatabaseConnector() as conn:
        existing = pd.read_sql_query(
            '''SELECT sha256_hash FROM media''', 
            conn,
        )
    return set([x.tobytes() for x in existing['sha256_hash'].values])


def path_queue_worker(path_queue, remove_after_upload):
    while True:
        event = path_queue.get()
        if event is None:
            break
        sha256_hash, fpath, fpath_original = event
        
        try:
            with DatabaseConnector() as conn:
                existing = pd.read_sql_query(
                    '''SELECT id, sha256_hash FROM media WHERE sha256_hash=%s''', 
                    conn,
                    params=(psycopg2.Binary(sha256_hash),),
                )
                if len(existing) == 0:
                    path_queue.put(event)
                    continue
                assert(len(existing) == 1)
                media_id = int(existing.iloc[0]['id'])

                existing_paths = pd.read_sql_query(
                    '''SELECT key_id FROM keys WHERE media_id=%s AND key=%s''', 
                    conn,
                    params=(media_id, fpath),
                )
                if len(existing_paths) == 0:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT INTO keys (media_id, key)
                        VALUES(%s, %s)
                        ;''',
                        (
                            media_id, fpath,
                        ),
                    )
                    conn.commit()
        except Exception:
            raise
        else:
            if remove_after_upload:
                os.remove(fpath_original)



def metadata_processor_worker(metadata_queue, s3_queue, path_queue, batch_size=50):
    '''
    Checks database for existing data in batches, and gives S3 uploaders work to do
    '''
    metadata_batch = []
    sha_256_hashes_this_session = set()  # Used to see if we are already uploading file in a different path in this current run
    
    while True:
        metadata = metadata_queue.get()
        if metadata is not None and metadata['sha256_hash'] in sha_256_hashes_this_session:
            path_queue.put((metadata['sha256_hash'], metadata['fpath_relative'], metadata['fpath']))

        if metadata is None or len(metadata_batch)+1 >= batch_size:
            if metadata is not None and metadata['sha256_hash'] not in sha_256_hashes_this_session:
                metadata_batch.append(metadata)
                sha_256_hashes_this_session.add(metadata['sha256_hash'])
            if len(metadata_batch) > 0:
                new_metadata_batch, existing_metadata_batch = batch_check_existing_media_rows(metadata_batch)
                # print(len(new_metadata_batch), len(existing_metadata_batch))
                for metadata_x in new_metadata_batch:
                    s3_queue.put(metadata_x)
                for metadata_x in existing_metadata_batch:
                    # No update logic for now, assume already existing and check path keys only
                    path_queue.put((metadata_x['sha256_hash'], metadata_x['fpath_relative'], metadata['fpath']))
                metadata_batch = []
            if metadata is None:
                break
        else:
            metadata_batch.append(metadata)
        

def batch_check_existing_media_rows(unfiltered_metadata_batch):
    with DatabaseConnector() as conn:
        existing = pd.read_sql_query(
            '''SELECT id, sha256_hash FROM media WHERE sha256_hash IN %s''', 
            conn,
            params=(tuple([psycopg2.Binary(d['sha256_hash']) for d in unfiltered_metadata_batch]),),
        )
        # print('%d existing out of %d' % (len(existing), len(unfiltered_metadata_batch)) )

        # existing_keys = pd.read_sql_query(
        #     '''SELECT * FROM keys WHERE key IN %s INNER JOIN media ON media.id=key.media_id''',
        #     conn,
        #     params=(tuple([d['fpath_relative'] for d in unfiltered_metadata_batch]),),
        # )

    new_metadata_batch = [d for d in unfiltered_metadata_batch if d['sha256_hash'] not in [bytes(b) for b in existing['sha256_hash'].values]]
    existing_metadata_batch = [d for d in unfiltered_metadata_batch if d['sha256_hash'] in [bytes(b) for b in existing['sha256_hash'].values]]

    return (new_metadata_batch, existing_metadata_batch)


def s3_upload_worker(s3_queue, path_queue):
    session = boto3.session.Session(
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
    )
    s3_client = session.client(
        "s3",
        config=config.boto_config,
        endpoint_url=config.s3_endpoint_url,
    )

    while True:
        metadata = s3_queue.get()
        if metadata is None:
            break

        if os.path.isfile(metadata['fpath']):
            try:
                response = s3_client.upload_file(metadata['fpath'], config.s3_bucket_name, metadata['fpath_relative'])
            except botocore.exceptions.ClientError as e:
                # logging.error(e)
                continue
        
        if 'thumbnail' in metadata and 'thumbnail_path' in metadata['thumbnail'] and os.path.isfile(metadata['thumbnail']['thumbnail_path']):
            fname, extension = os.path.splitext(metadata['fpath_relative'])
            thumb_key = fname + '-%dw_%dh' % (metadata['thumbnail']['thumbnail_width'], metadata['thumbnail']['thumbnail_height']) + extension
            try:
                response = s3_client.upload_file(metadata['thumbnail']['thumbnail_path'], config.s3_bucket_name, thumb_key)
                os.remove(metadata['thumbnail']['thumbnail_path'])
            except botocore.exceptions.ClientError as e:
                # logging.error(e)
                continue
            
        # S3 uploads good, now do database stuff
        if metadata['media_type'] == 'image':
            media_type = 0
        elif metadata['media_type'] == 'video':
            media_type = 1

        with DatabaseConnector() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO media (sha256_hash, creation_time, media_type, file_size, height, width, latitude, longitude, s3_key)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ;''',
                (
                    metadata['sha256_hash'], metadata['creation_time'], media_type, metadata['size'],
                    metadata['height'], metadata['width'], metadata['lat'], metadata['lon'],
                    metadata['fpath_relative'],
                ),
            )
            conn.commit()
            existing = pd.read_sql_query(
                '''SELECT id, sha256_hash FROM media WHERE sha256_hash=%s''', 
                conn,
                params=(psycopg2.Binary(metadata['sha256_hash']),),
            )
            assert(len(existing) == 1)
            media_id = int(existing.iloc[0]['id'])

            cursor.execute(
                '''INSERT INTO thumbnail (media_id, key, height, width, file_size)
                VALUES(%s, %s, %s, %s, %s);''',
                (
                    media_id, thumb_key, int(metadata['thumbnail']['thumbnail_height']),
                    int(metadata['thumbnail']['thumbnail_width']), int(metadata['thumbnail']['thumbnail_size']),
                ),
            )

            if metadata['media_type'] == 'video':
                cursor.execute(
                    '''INSERT INTO videos (id, duration)
                    VALUES(%s, %s);''',
                    (
                        media_id, metadata['video_only']['duration'],
                    ),
                )

            if metadata['media_type'] == 'image':
                cursor.execute(
                    '''INSERT INTO images (id,
                    average_hash1, average_hash2, average_hash3, average_hash4,
                    difference_hash1, difference_hash2, difference_hash3, difference_hash4,
                    perceptual_hash1, perceptual_hash2, perceptual_hash3, perceptual_hash4
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);''',
                    (
                        media_id,
                        metadata['image_only']['hashes']['average'][:4],
                        metadata['image_only']['hashes']['average'][4:8],
                        metadata['image_only']['hashes']['average'][8:12],
                        metadata['image_only']['hashes']['average'][12:16],
                        metadata['image_only']['hashes']['difference'][:4],
                        metadata['image_only']['hashes']['difference'][4:8],
                        metadata['image_only']['hashes']['difference'][8:12],
                        metadata['image_only']['hashes']['difference'][12:16],
                        metadata['image_only']['hashes']['perceptual'][:4],
                        metadata['image_only']['hashes']['perceptual'][4:8],
                        metadata['image_only']['hashes']['perceptual'][8:12],
                        metadata['image_only']['hashes']['perceptual'][12:16],
                    ),
                )
            
            conn.commit()
            cursor.close()

        print('S3 upload complete:', os.path.basename(metadata['fpath']))
        path_queue.put((metadata['sha256_hash'], metadata['fpath_relative'], metadata['fpath']))


def combine_queues(main_queue, secondary_queue):
    while True:
        main_queue.put(secondary_queue.get())


def walk_dir(root_dir, queue, existing_hashes, remove_after_upload):
    assert(os.path.isdir(root_dir))
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for fpath in [os.path.join(dirpath, filename) for filename in filenames]:
            if path_is_image_or_video(fpath):
                if len(existing_hashes) > 0:                 
                    with open(fpath, "rb") as f:
                        file_hash = hashlib.sha256()
                        while chunk := f.read(64*16):
                            file_hash.update(chunk)
                    sha_hash = file_hash.digest()
                    if sha_hash in existing_hashes:
                        if remove_after_upload:
                            os.remove(fpath)
                        pass
                    else:
                        queue.put(watchdog.events.FileCreatedEvent(os.path.abspath(fpath)))
                else:
                    queue.put(watchdog.events.FileCreatedEvent(os.path.abspath(fpath)))


def path_is_image_or_video(fpath):
    bytes = filetype.utils.get_bytes(fpath)
    if filetype.helpers.is_image(bytes):
        return True
    elif filetype.helpers.is_video(bytes):
        return True
    else:
        return False


class DatabaseConnector():
    '''
    Allows psycopg2 both with or without SSH tunneling
    '''
    def __init__(self):
        self.postgres_over_ssh = config.postgres_over_ssh
        if self.postgres_over_ssh:
            self.ssh_host = config.ssh_host
            self.ssh_username = config.ssh_username
            self.ssh_key = config.ssh_key_path
            self.local_bind_port = None
            self.postgres_host = '127.0.0.1'
        else:
            self.local_bind_port = 5432
            self.postgres_host = config.postgres_host

        self.database_name = config.database_name
        self.postgres_user = config.postgres_user
        self.postgres_pass = config.postgres_pass

    def __enter__(self):
        if self.postgres_over_ssh:
            self.server = SSHTunnelForwarder(
                self.ssh_host,
                ssh_username=self.ssh_username,
                ssh_pkey=self.ssh_key,
                remote_bind_address=('127.0.0.1', 5432)
            )
            self.server.start()
            self.local_bind_port = self.server.local_bind_port

        self.conn = psycopg2.connect(
            dbname=self.database_name,
            user=self.postgres_user,
            password=self.postgres_pass,
            port=self.local_bind_port,
            host=self.postgres_host,
        )
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        if self.postgres_over_ssh:
            self.server.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Command line tool to upload pictures')
    parser.add_argument(
        'root_directory',
        help='Base directory to base key relative paths off of'
    )
    parser.add_argument(
        'subdir_to_scan', default=[], nargs='*',
        help='Only scan for new photos in these subdirectories',
    )
    parser.add_argument(
        '--monitor_new', action='store_true', default=False,
        help='Keep running, monitoring for new files',
    )
    parser.add_argument(
        '--check_existing_hashes', action='store_true', default=False,
        help='During initial walk, remove files already in DB',
    )
    parser.add_argument(
        '--remove_after_upload', action='store_true', default=False,
        help='Remove files from local disk after processing',
    )
    parser.add_argument(
        '--start_date', default=None,
        help='Only process media newer than this date',
        type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d'),
    )
    parser.add_argument(
        '--num_processing_threads', default=4, type=int,
    )
    args = parser.parse_args()
    assert(os.path.isdir(args.root_directory))
    if len(args.subdir_to_scan) > 0:
        for subdir_to_scan in args.subdir_to_scan: 
            assert(os.path.isdir(subdir_to_scan))

    dm = DirectoryMonitor(
        args.root_directory, subdirs_only=args.subdir_to_scan, monitor_new=args.monitor_new,
        start_date=args.start_date, num_processing_threads=args.num_processing_threads,
        remove_after_upload=args.remove_after_upload, check_existing_hashes=args.check_existing_hashes,
    )

    if args.monitor_new:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            dm.observer.stop()
        dm.observer.join()