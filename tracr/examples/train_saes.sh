#!/bin/bash

# run asynchronously
python train_saes.py 0 49 --suffix 0 --device 3 &
python train_saes.py 50 99 --suffix 1 --device 1 &
python train_saes.py 100 149 --suffix 2 --device 2 &
python train_saes.py 150 199 --suffix 3 --device 3 &
python train_saes.py 200 249 --suffix 4 --device 3 &
python train_saes.py 250 299 --suffix 5 --device 1 &
python train_saes.py 300 349 --suffix 6 --device 2 &
python train_saes.py 350 399 --suffix 7 --device 3 &
python train_saes.py 400 449 --suffix 8 --device 3 &
python train_saes.py 450 499 --suffix 9 --device 1 &
python train_saes.py 500 549 --suffix 10 --device 2 &
python train_saes.py 550 599 --suffix 11 --device 3 &
python train_saes.py 600 649 --suffix 12 --device 3 &
python train_saes.py 650 699 --suffix 13 --device 1 &
python train_saes.py 700 749 --suffix 14 --device 2 &
python train_saes.py 750 799 --suffix 15 --device 3 &
python train_saes.py 800 849 --suffix 16 --device 3 &
python train_saes.py 850 899 --suffix 17 --device 1 &
python train_saes.py 900 949 --suffix 18 --device 2 &
python train_saes.py 950 999 --suffix 19 --device 3 &

# wait for all processes to finish
wait

echo "Done"