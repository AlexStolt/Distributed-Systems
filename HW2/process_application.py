from process_api import *
import sys
import random

if __name__ == '__main__':
  if len(sys.argv) != 3:
    print("python3 <EXECUTABLE> <IP> <PORT>")
    exit(-1)

  TCP_UNICAST_HOST = sys.argv[1]
  TCP_UNICAST_PORT = int (sys.argv[2])


  api_init(TCP_UNICAST_HOST, TCP_UNICAST_PORT)



  
  fd1 = grp_join('sports', ''.join(random.choice(string.ascii_lowercase) for i in range(10)))
  # fd2 = grp_join('ski', ''.join(random.choice(string.ascii_lowercase) for i in range(10)))
  message = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
  # time.sleep(2)
  grp_send(fd1, message, len(message), 0)
  time.sleep(4)
  
  while True:
    message, length = grp_recv(fd1, 0)
    if length < 0:
      continue
    print(message, length)
  # grp_send(fd1, message, len(message), 0)
  time.sleep(100)

  

