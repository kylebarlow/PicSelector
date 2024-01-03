#!/bin/bash

# This trap business sems to not catch docker-compose down signals
trap 'echo "Caught trap signal"' SIGHUP SIGINT SIGQUIT SIGTERM

while :
do
   echo "Starting Python script"
   date
   nice python3 /webwork/picture_functions.py no_root_dir --num_processing_threads 1 --remove_after_upload --check_existing_hashes --check_existing_keys --sub_keys_to_scan kyle_phone_direct/2310_p6p malia_phone_direct/2310_p4a
   echo "Python script finished"
   date
   # 20 hours = 72000 seconds
   sleep 72000 &
   wait $!
done
