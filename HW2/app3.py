from email import message
from time import sleep
from process_api import *
import sys
import random

def application():
  fd = grp_join('basket', ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
  time.sleep(2)
  message = ''.join(random.choice(string.ascii_lowercase) for i in range(5))
  print(threading.get_ident(), '->', message)
  bytes = grp_send(fd, message, len(message))
  while True:
    message, length = grp_recv(fd, 0, 1)
    if length < 0:
      continue
    print(threading.get_ident(), '<-', message)

if __name__ == '__main__':
  if len(sys.argv) != 2:
    print("python3 <EXECUTABLE> <IP>")
    exit(-1)

  HOST_IP = sys.argv[1]
  
  api_init(HOST_IP)
  
  threads = []
  for i in range(2):
    threads.append(threading.Thread(target=application, args=()))
    threads[-1].start()
  
  for thread in threads:
    thread.join()
  