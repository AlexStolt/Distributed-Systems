from time import sleep
from process_api import *
import sys
import random


def sender_application(fd, iterations):
  for i in range(iterations):
    message = input("Type a Message: ")
    grp_send(fd, message, len(message))
  

def receiver_application(block, fd, iterations):
  # time.sleep(20)
  #Wait to start 10 seconds  
  if not block:
    while True:
      message, length = grp_recv(fd, block, 1)
      if length < 0:
        if block:
          print(length)
        continue
      
      print()
      print(f'\033[92m{message}\033[00m')
      
  else:
    while True:
      message, length = grp_recv(fd, block, 1)      
      print(f'\033[92m{message}\033[00m')
  


if __name__ == '__main__':
  if len(sys.argv) != 2:
    print("python3 <EXECUTABLE> <IP>")
    exit(-1)

  HOST_IP = sys.argv[1]
  example = 1
  
  api_init(HOST_IP)
 
  # TOTAL CAUSAL non blocking receive 
  if example == 1:
    fd = grp_join('basket', ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
    t1 = threading.Thread(target=sender_application, args=(fd, 20,))
    t2 = threading.Thread(target=receiver_application, args=(0, fd, 20))

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("finish example 1")
  
  elif example == 2:
    fd = grp_join('basket', ''.join(random.choice(string.ascii_lowercase) for i in range(4)))

    t1 = threading.Thread(target=sender_application, args=(fd, 20,))
    t2 = threading.Thread(target=receiver_application, args=(1, fd, 20))

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("finish example 2")
  elif example == 3:
    fd = grp_join('basket', ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
    time.sleep(5)
    grp_leave(fd)

  
  time.sleep(10000)
  
  

  

