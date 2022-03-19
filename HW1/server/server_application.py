from server_api import *

WORKER_THREADS = 3

SERVER_FAILURE = True


def prime(services):

    i = 0
    while True:
        for service in services:
            id, buffer, length, flags = get_request(service)
            if id < 0:
                continue
            
            number = int.from_bytes(buffer, "big")
            print(f"\033[96mPrimitive Test is Running for Request({id}) and Number: {number}\033[00m")
            
            # ****** [Enable for Testing]: Backup and Ping ****** 
            
            #time.sleep(10)
            # time.sleep(10)
            # unregister(20)
            # time.sleep(10)
            # register(20)
            
            number_is_prime = True
            for i in range(2, number):
                if get_request_status_flag(id):
                    print('[Client Aborted]: Application Computation Stops')
                    break
                
                # ****** [Enable for Testing]: Client Aborts ****** 
                # time.sleep(10)
                
                if (number % i) != 0:
                    continue
                number_is_prime = False
                break
       
            if number_is_prime:
                response = 'Number {number}: Prime'.format(number=number)
            else:
                response = 'Number {number}: Not Prime'.format(number=number)

            send_reply(id, response, len(response))
            
            i = i + 1

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

    # Currently Not Executed Function
    api_destroy()
