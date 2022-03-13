from server_api import *
import sys

def isprime(buffer):
    for n in range(2,int(int(buffer)**0.5)+1):
        if int(buffer)%n==0:
            buffer = buffer + " is not prime!"
            return buffer

    buffer = buffer + " is prime!"
    return buffer

if __name__ == '__main__':
    

    register(10)
    register(20)
    time.sleep(10)
  
    id, buffer, len = get_request(20)
    if id < 0:
        print ("Expired Requests")
        exit(1)


    
    #buffer = isprime(buffer)
    buffer = "Hello from server"
    
    time.sleep(10)
    send_reply(id, buffer,REQUEST_LENGTH)
    print(requests)
    print_services()
    
