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
    sleep(random.randint(0, 4))
    fd = nfs_open("random.txt", O_RDONLY)
    print(fd)
    print(nfs_read(fd, 20))


if __name__ == '__main__':
    nfs_init("127.0.0.1", 8080, 1, 1, 1)
    
   
    
    
    # print(nfs_open("random.txt", O_CREAT))
    for _ in range(4):
        threading.Thread(target=create_file).start()
    