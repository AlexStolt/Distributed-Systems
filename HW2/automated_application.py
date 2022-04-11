from time import sleep
from process_api import *
import sys
import random

rage_mutex = threading.Lock()

BLOCKING = True
TOTAL_CAUSAL = True


def sender_application(fd, name, iterations):

  for iteration in range(iterations):
    message = f'{name} at {iteration}'
    grp_send(fd, message, len(message))
    sleep(1)
  

def receiver_application(fd):
  while True:
    source, message, length = grp_recv(fd, BLOCKING, TOTAL_CAUSAL)
    # print(length)
    if length < 0:
      continue
    
    print(f'\033[92m{message}\033[00m')


if __name__ == '__main__':
  HOST_IP = sys.argv[1]
  
  api_init(HOST_IP)
  
  # name = input('Enter your Name: ')
  # group = input('Enter a Group to Join: ')
  # iterations = int(input('Enter Iterations: '))
  
  name = f'{random.randint(1, 1000)}'
  group = '2'
  iterations = 10
  # Join Group
  fd = grp_join(group_name=group, process_id=name)
   
  sender_thread = threading.Thread(target=sender_application, args=(fd, name, iterations, ))
  receiver_thread = threading.Thread(target=receiver_application, args=(fd, ))
  
  sender_thread.start()
  receiver_thread.start()
  
  sender_thread.join()
  receiver_thread.join()