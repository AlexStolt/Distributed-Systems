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




  fd = grp_join('sports', ''.join(random.choice(string.ascii_lowercase) for i in range(3)))
  time.sleep(100)

  

