from time import sleep
from process_api import *
import sys
import random

def main_application(group_name, block, fd):
  fd = grp_join(group_name, ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
  # time.sleep(random.randint(10,20))
  message = ''.join(random.choice(string.ascii_lowercase) for i in range(8))
  
  
  time.sleep(2)
  while True:
    message, length = grp_recv(fd, block, 1)
    if length < 0:
      if block:
        print(length)
      continue
    
    print(f'\033[92m{message} -> {group_name} -> {length}\033[00m')
  
  return
  message = ''.join(random.choice(string.ascii_lowercase) for i in range(8))
  
  grp_send(fd, message, len(message), 1)
  time.sleep(2)
  print(grp_recv(fd, 0, 1))
  
  message = ''.join(random.choice(string.ascii_lowercase) for i in range(8))
  grp_send(fd, message, len(message), 1)
  time.sleep(20)
  print(grp_recv(fd, 0, 1))
  # while True:
  #   message, length = grp_recv(fd, block)
  #   if length < 0:
  #     if block:
  #       print(length)
  #     continue
    
  #   print(f'\033[92m{message} -> {group_name} -> {length}\033[00m')
    


if __name__ == '__main__':
  if len(sys.argv) != 2:
    print("python3 <EXECUTABLE> <IP>")
    exit(-1)

  HOST_IP = sys.argv[1]

  api_init(HOST_IP)
  # fd1 = grp_join("basket", ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
  # fd2 = grp_join("soccer", ''.join(random.choice(string.ascii_lowercase) for i in range(4)))
  
  
  # grp_send(fd2, "second_message", 9, 0)
  # time.sleep(2)
  
  
  t1 = threading.Thread(target=main_application, args=('basket', 0, 0, ))
  # t2 = threading.Thread(target=main_application, args=('basket', 0, 0, ))
  
  t1.start()
  # t2.start()
  # # print(fd1, fd2)
  # while True:
  #   message1, length1 = grp_recv(fd1, 0)
  #   if length1 >= 0:
  #     print(f'\033[91m{message1} -> basket -> {length1}\033[00m')
    
  #   message2, length2 = grp_recv(fd2, 1)
  #   if length2 >= 0:
  #     print(f'\033[91m{message2} -> soccer -> {length2}\033[00m')
  #   else:
  #     print(length2)
    
  # for i in range(10):    
    # grp_send(fd1, f"{i}", 8, 1)
    # time.sleep(10)
    # print('Second Is Sent')
  # grp_send(fd1, "second message", 8, 1)
 
 
  t1.join()
  # t2.join()
  
  
  
  
  
  # fd1 = grp_join('sports', ''.join(random.choice(string.ascii_lowercase) for i in range(10)))
  # # fd2 = grp_join('ski', ''.join(random.choice(string.ascii_lowercase) for i in range(10)))
  # message = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
  # # time.sleep(2)
  # grp_send(fd1, message, len(message), 0)
  time.sleep(10000)
  
  

  

