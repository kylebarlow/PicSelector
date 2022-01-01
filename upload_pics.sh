#!/bin/bash

date >> ~/upload_pics_log
~/PicSelector/pics_venv/bin/python3 ~/PicSelector/picture_functions.py /home/mediaupload /home/mediaupload/kyle_phone --num_processing_threads 1 --remove_after_upload >> ~/upload_pics_log
~/PicSelector/pics_venv/bin/python3 ~/PicSelector/picture_functions.py /home/mediaupload /home/mediaupload/malia_phone --num_processing_threads 1 --remove_after_upload >> ~/upload_pics_log
date >> ~/upload_pics_log
echo >> ~/upload_pics_log
