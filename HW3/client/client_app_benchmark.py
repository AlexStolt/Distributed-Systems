from pickletools import string1
from time import sleep
from client_api import *
import random
import string
import timeit


def random_string():
  letters = string.ascii_lowercase
  str = ''.join(random.choice(letters) for i in range(508))
  str = str + '.txt'
    
  return str

def read_bench(fd):
  nfs_read(fd, 512)
  nfs_seek(fd, 0, SEEK_SET)
  
  start = timeit.default_timer()
  
  nfs_read(fd, 512)
  
  stop = timeit.default_timer()
  print('Read: ', stop - start)  


def write_bench(fd):
  string1 = random_string()
  start = timeit.default_timer()
  
  nfs_write(fd, string1, 512)
  
  stop = timeit.default_timer()
  print('Write: ', stop - start)


if __name__ == '__main__':
  try:
      cache_blocks        = int(sys.argv[1])
      cache_block_size    = int(sys.argv[2])
      cache_fresh_t       = float(sys.argv[3])
  except:
      print("python3 <TOTAL BLOCKS> <BLOCK SIZE> <FRESH TIME>")
      exit(0)


  nfs_init("127.0.0.1", 8080, cache_blocks, cache_block_size, cache_fresh_t)
  fd = nfs_open('files/input_test.txt', O_RDWR)
  if fd < 0:
    exit(0)
  read_bench(fd)
  write_bench(fd)
 