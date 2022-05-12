from time import sleep
from client_api import *
import random
import string
import timeit


def read_bench():
  fd = nfs_open('files/input_test.txt', O_RDWR)
  
  nfs_read(fd, 512)
  nfs_seek(fd, 0, SEEK_SET)
  
  start = timeit.default_timer()
  
  print(nfs_read(fd, 512))
  
  stop = timeit.default_timer()
  print('Time: ', stop - start)  


if __name__ == '__main__':
  try:
      cache_blocks        = int(sys.argv[1])
      cache_block_size    = int(sys.argv[2])
      cache_fresh_t       = int(sys.argv[3])
  except:
      print("python3 <TOTAL BLOCKS> <BLOCK SIZE> <FRESH TIME>")
      exit(0)


  nfs_init("127.0.0.1", 8080, cache_blocks, cache_block_size, cache_fresh_t)
  
  read_bench()
 