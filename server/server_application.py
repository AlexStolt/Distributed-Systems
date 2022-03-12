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
    register(20)
    unregister(30)
    time.sleep(20)
    #for x in range(5):
    #time.sleep(3)
    id, buffer, len = get_request(20)
    #print(id)
    print(buffer)
    buffer = "Hello from server"
    send_reply(id, buffer, 18)
    print(requests)
    print_services()
    
