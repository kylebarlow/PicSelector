import os
import datetime
import sys
import io
import time
import hashlib
import multiprocessing
from pprint import pprint

import filetype
import watchdog
import watchdog.events
import watchdog.observers
import PIL
from PIL.ExifTags import TAGS, GPSTAGS
import imagehash
# import face_recognition
from dateutil import parser as dateutil_parser
import ffmpeg


def process_media_file(event):
    fpath = event.src_path

    if filetype.helpers.is_image(fpath):
        # with open(fpath, 'rb') as f:
        #     fdata = f.read()
        # process_image(fpath, fdata)
        pass
    elif filetype.helpers.is_video(fpath):
        pprint(process_video(fpath))


def process_video(fpath):
    info = find_probe_info(ffmpeg.probe(fpath), desired_keys=['duration', 'location', 'creation_time', 'height', 'width'])
    # pprint(ffmpeg.probe(fpath))

    with open(fpath, "rb") as f:
        file_hash = hashlib.sha256()
        while chunk := f.read(64*16):
            file_hash.update(chunk)
    sha_hash = file_hash.hexdigest()

    date_time = None
    if 'creation_time' in info:
        date_time = dateutil_parser.parse((info['creation_time'][0]))

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

    filesize = os.path.getsize(fpath)

    return {
        'lat': lat,
        'lon': lon,
        'height': height,
        'width': width,
        'size': filesize,
        'sha256_hash': sha_hash,
        'creation_time': date_time,
        'video_length': duration,
        'media_type' : 'video',
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
                if k.startswith(desired_key):
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


def process_image(fpath, fdata, max_thumbnail_width=400):
    sha_hash = hashlib.sha256(fdata).hexdigest()
    image = PIL.Image.open(io.BytesIO(fdata))
    hashes = {}
    hashes['average'] = str(imagehash.average_hash(image))
    hashes['perceptual'] = str(imagehash.phash(image))
    hashes['difference'] = str(imagehash.dhash(image))

    exif_data = image.getexif()
    exif_dict = {}
    for tag_id, data in exif_data.items():
        # get the tag name, instead of human unreadable tag id
        tag = PIL.ExifTags.TAGS.get(tag_id, tag_id)
        if tag == 'GPSInfo':
            continue
        if isinstance(data, bytes):
            data = data.decode()
        exif_dict[tag] = data

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

    date_time = set([value for key, value in exif_dict.items() if key.startswith('DateTime')])
    assert(len(date_time) <= 1)
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

    max_size = (max_thumbnail_width, min(max_thumbnail_width*3, image.height))
    thumbnail = image.copy().thumbnail(max_size)

    # fr_image = face_recognition.load_image_file(io.BytesIO(fdata))
    # face_locations = face_recognition.face_locations(fr_image)
    # face_encodings = face_recognition.face_encodings(fr_image, num_jitters=3)
    
    print(fpath, sha_hash, date_time)
    # print(face_locations)
    # print(face_encodings)
    print(hashes)
    print(image.width, image.height, image.mode, image.format)
    print(exif_dict)
    print(lat, lon)
    if len(geotags) > 0:
        print(geotags)
    # metadata = pyexiv2.ImageMetadata(fdata)
    # metadata.read()
    # print(metadata.exif_keys)
    print()


class DirectoryMonitor():
    def __init__(self, root_dir, add_existing_files=True, monitor_new=True, max_file_queue_size=100, num_processing_threads=2, processing_niceness=10):
        assert(os.path.isdir(root_dir))
        self.root_dir = root_dir
        self.add_existing_files = add_existing_files
        self.queue = multiprocessing.Queue(maxsize=max_file_queue_size)
        self.watchdog_queue = multiprocessing.Queue()
        self.num_processing_threads = num_processing_threads
        if monitor_new:
            self.initialize_watchdog()
            self.queue_combiner = multiprocessing.Process(target=combine_queues, args=(self.queue, self.watchdog_queue))
            self.queue_combiner.start()
        else:
            assert(add_existing_files)

        if self.add_existing_files:
            self.initial_walker = multiprocessing.Process(target=walk_dir, args=(self.root_dir, self.queue))
            self.initial_walker.start()

        self.media_process_pool = multiprocessing.Pool(
            processes=self.num_processing_threads,
            initializer=media_processor_worker,
            initargs=(self.queue, processing_niceness)
        )

        if not monitor_new:
            self.exit_when_initial_processing_done()

    def exit_when_initial_processing_done(self):
        self.initial_walker.join()
        number_times_queue_0 = 0
        while number_times_queue_0 < 5:
            time.sleep(0.4)
            if self.queue.qsize() == 0:
                number_times_queue_0 += 1
        for i in range(self.num_processing_threads):
            self.queue.put(None)
        self.media_process_pool.close()
        self.media_process_pool.join()

    def initialize_watchdog(self):
        self.event_handler = FileWatchdog(self.watchdog_queue)
        self.observer = watchdog.observers.Observer()
        self.observer.schedule(self.event_handler, self.root_dir, recursive=True)
        self.observer.start()


class FileWatchdog(watchdog.events.PatternMatchingEventHandler):
    def __init__(self, queue, **kwargs):
        super().__init__(**kwargs)
        self.queue = queue

    def process(self, event):
        if path_is_image_or_video(event.src_path):
            self.queue.put(event)
        # return super().process(event)

    def on_created(self, event):
        self.process(event)
        # return super().process(event)


def media_processor_worker(q, niceness):
    os.nice(niceness)
    while True:
        event = q.get()
        if event is None:
            break
        process_media_file(event)


def combine_queues(main_queue, secondary_queue):
    while True:
        main_queue.put(secondary_queue.get())


def walk_dir(root_dir, queue):
    assert(os.path.isdir(root_dir))
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for fpath in [os.path.join(dirpath, filename) for filename in filenames]:
            if path_is_image_or_video(fpath):
                queue.put(watchdog.events.FileCreatedEvent(os.path.abspath(fpath)))


def path_is_image_or_video(fpath):
    bytes = filetype.utils.get_bytes(fpath)
    if filetype.helpers.is_image(bytes):
        return True
    elif filetype.helpers.is_video(bytes):
        return True
    else:
        return False


if __name__ == '__main__':
    monitor_new = False
    dm = DirectoryMonitor(sys.argv[1], monitor_new=monitor_new)
    if monitor_new:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            dm.observer.stop()
        dm.observer.join()