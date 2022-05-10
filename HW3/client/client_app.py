from time import sleep
from client_api import *
import random
import string

def random_string():
    letters = string.ascii_lowercase
    str = ''.join(random.choice(letters) for i in range(10))
    str = str + '.txt'
    
    return str

def create_file():
    sleep(2)
    fd = nfs_open("random.txt", O_RDWR)
    print("File Descriptor:", fd)

    # nfs_seek(fd, 3, SEEK_SET)
    # print(nfs_read(fd, 20))
    
    # nfs_seek(fd, 2, SEEK_CUR)
    # print(nfs_read(fd, 20))
    
    # nfs_seek(fd, 2, SEEK_END)
    # print(nfs_read(fd, 4))
    
    buffer = "From 23 and Show on"
    nfs_seek(fd, 12, SEEK_END)
    print(nfs_write(fd, buffer, 11))
    print(nfs_write(fd, buffer, 11))
    # sleep(10)
    
    # print(nfs_write(fd, buffer, 11))
    
    
    print("END OF THREAD")


if __name__ == '__main__':
    # cache_blocks = int(sys.argv[1])
    try:
        cache_blocks        = int(sys.argv[1])
        cache_block_size    = int(sys.argv[2])
        cache_fresh_t       = int(sys.argv[3])
    except:
        print("python3 <TOTAL BLOCKS> <BLOCK SIZE> <FRESH TIME>")
        exit(0)

        
    nfs_init("127.0.0.1", 8080, cache_blocks, cache_block_size, cache_fresh_t)
           
    
    # print(nfs_open("random.txt", O_CREAT))
    for _ in range(1):
        threading.Thread(target=create_file).start()
    