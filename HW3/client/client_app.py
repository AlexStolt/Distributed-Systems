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
    fd = nfs_open("files/test1.txt", O_RDWR)
    print("File Descriptor:", fd)

    nfs_seek(fd, 3, SEEK_SET)
    print(nfs_read(fd, 20))
    
    time.sleep(2)
    
    nfs_seek(fd, 6, SEEK_SET)
    print(nfs_read(fd, 10))
    
    
    
    # nfs_seek(fd, 2, SEEK_CUR)
    # print(nfs_read(fd, 20))
    
    # nfs_seek(fd, 2, SEEK_END)
    # print(nfs_read(fd, 4))
    
    # buffer = "Hello World"
    # nfs_seek(fd, 12, SEEK_END)
    # print(nfs_write(fd, buffer, 11))
    # print(nfs_write(fd, buffer, 11))
    # sleep(10)
    
    # print(nfs_write(fd, buffer, 11))
    
    
    print("END OF THREAD")

def lookup_test():
    # Create
    fd = nfs_open("files/test1.txt", O_CREAT | O_TRUNC | O_RDWR)
    print("File Descriptor:", fd)
    

def test_read():
    pass



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

    fd = nfs_open('files/command_line.txt', O_RDWR)   
    
    print(fd)
    while True:
        command = input('Command (Type -h or --help for help): ')
        if command == '-h' or command == '--help':
            print('************** [HELP] **************')
            print('1. Read: (r <length>)')
            print('2. Write: (w <buffer> <length>)')
            print('3. Seek: (s <offset> <s/c/e>)')
            print('4. Truncate: (t <length>)')
            print('5. Close: (c)')
            print('************************************')
            continue
        
        # if command == 'O' or command == 'o':
        #     path =  input('Path: ')
        #     flags = flags[input('Flags: ')]
        command_fields = command.split(' ')
        if command_fields[0] == 'r': 
            if len(command_fields) < 2:
                continue
            data, bytes_read = nfs_read(fd, int(command_fields[1]))
            print(f'Read {bytes_read} Bytes: {data}')
        
        elif command_fields[0] == 'w': 
            if len(command_fields) < 3:
                continue
            bytes_written = nfs_write(fd, command_fields[1], int(command_fields[-1]))
            print(f'Written {bytes_written} Bytes')
            
        elif command_fields[0] == 's': 
            if command_fields[2] == 's':
                nfs_seek(fd, int(command_fields[1]), SEEK_SET)
            elif command_fields[2] == 'c':
                nfs_seek(fd, int(command_fields[1]), SEEK_CUR)
            elif command_fields[2] == 'e':
                nfs_seek(fd, int(command_fields[1]), SEEK_END)
        elif command_fields[0] == 't':
            if len(command_fields) < 2:
                continue
            status = nfs_ftruncate(fd, int(command_fields[1]))
            print(f'Truncate Status: {status}')
        elif command_fields[0] == 'c':
            if len(command_fields) > 1:
                continue
            status = nfs_close(fd)
            print('Close Status:', status)
            # print(f'Written {bytes_written} Bytes')
    
    # lookup_test()
    
    # print(nfs_open("random.txt", O_CREAT))
    # for _ in range(1):
    #     threading.Thread(target=create_file).start()
    