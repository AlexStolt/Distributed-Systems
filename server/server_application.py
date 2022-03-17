from urllib import response
from server_api import *
import sys

WORKER_THREADS = 3

def prime(services):
    while True:
        for service in services:
            id, buffer, length, flags = get_request(service)
            if id < 0:
                continue
            number = int.from_bytes(buffer, "big")
            print("Primitive Test is Running for Number:", number)
            
            number_is_prime = True
            for i in range(2, number):
                if (number % i) != 0:
                    continue
                number_is_prime = False
                break
            
            # time.sleep(10)
            # print(flags.get_abort())


            if number_is_prime:
                response = 'Number {number}: Prime'.format(number=number)
            else:
                response = 'Number {number}: Not Prime'.format(number=number)
            
            send_reply(id, response, len(response))

if __name__ == '__main__':
    services = [20]
    threads = []

    # Register Services
    for service in services:
        register(service)
    

    for _ in range(WORKER_THREADS):
        threads.append(threading.Thread(target=prime, args=(services, )))
        threads[-1].start()

    for thread in threads:
        thread.join()