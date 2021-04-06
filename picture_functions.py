import os
import datetime
import sys
import io
import time
import hashlib
import multiprocessing

import filetype
import watchdog
import watchdog.events
import watchdog.observers
import PIL
from PIL.ExifTags import TAGS, GPSTAGS
import imagehash
# import face_recognition


def process_media_file(event):
    fpath = event.src_path
    with open(fpath, 'rb') as f:
        fdata = f.read()

    if filetype.helpers.is_image(fdata):
        process_image(fpath, fdata)


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
    # TODO
    # face recognition
    # GPS

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
    def __init__(self, root_dir, add_existing_files=True, max_file_queue_size=100, num_processing_threads=2, processing_niceness=10):
        assert(os.path.isdir(root_dir))
        self.root_dir = root_dir
        self.add_existing_files = add_existing_files
        self.queue = multiprocessing.Queue(maxsize=max_file_queue_size)
        self.watchdog_queue = multiprocessing.Queue()
        self.initialize_watchdog()

        self.queue_combiner = multiprocessing.Process(target=combine_queues, args=(self.queue, self.watchdog_queue))
        self.queue_combiner.start()
        if self.add_existing_files:
            self.initial_walker = multiprocessing.Process(target=walk_dir, args=(self.root_dir, self.queue))
            self.initial_walker.start()

        self.media_process_pool = multiprocessing.Pool(
            processes=num_processing_threads,
            initializer=media_processor_worker,
            initargs=(self.queue, processing_niceness)
        )

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
        process_media_file(event)


def combine_queues(main_queue, secondary_queue):
    while True:
        main_queue.put(secondary_queue.get())


def walk_dir(root_dir, queue):
    found_files = {'images': [], 'videos': []}
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
    dm = DirectoryMonitor(sys.argv[1])
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        dm.observer.stop()
    dm.observer.join()