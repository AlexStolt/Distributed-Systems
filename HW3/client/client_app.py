from client_api import *
import random
import string

def random_string():
    letters = string.ascii_lowercase
    str = ''.join(random.choice(letters) for i in range(10))
    str = str + '.txt'
    
    return str


if __name__ == '__main__':
    nfs_init("127.0.0.1", 8080, 1, 1, 1)
    print(nfs_open(random_string(), O_CREAT))
    print(nfs_open(random_string(), O_CREAT))
    pass
    