from time import sleep
from client_api import *
import random
import string


# Cache Information
cache_blocks = 4
cache_fresh_t = 1
cache_block_size = 10



def random_string():
    letters = string.ascii_lowercase
    str = ''.join(random.choice(letters) for i in range(10))
    str = str + '.txt'
    
    return str

def create_file():
    # sleep(random.randint(0, 4))
    fd = nfs_open("random.txt", O_RDWR)
    # print(fd)
    # nfs_seek(fd, 3, SEEK_SET)
    # print(nfs_read(fd, 4))
    
    # sleep(4)
    buffer = "Hello-from-Client"
    nfs_seek(fd, 12, SEEK_SET)
    nfs_write(fd, buffer, 11)
    
    # buffer = "Hello-from-Client"
    # nfs_seek(fd, 12, SEEK_SET)
    # nfs_write(fd, buffer, 11)
    
    nfs_seek(fd, 4, SEEK_SET)
    print(nfs_read(fd, 15))
    


if __name__ == '__main__':
    nfs_init("127.0.0.1", 8080, cache_blocks, cache_block_size, cache_fresh_t)
    
   
    
    
    # print(nfs_open("random.txt", O_CREAT))
    for _ in range(1):
        threading.Thread(target=create_file).start()
    