#!/bin/bash

INIT=9000

for ((c = 0; c < 4; c++))
do  
  INIT=$((INIT + 1))
  python3 process_application.py 127.0.0.1 $INIT &
  sleep(1)
done