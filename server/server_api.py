from locale import atoi
from os import pread
import socket
import struct
import threading
import time
import sys
import select
from typing import Any
from dataclasses import dataclass

# Global Variables
services = []
requests  = []

REQUEST_LENGTH = 1024
LOAD = 0
REQUEST_SEQUENCE = 0

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 8000

SERVER_IP = None
UNICAST_PORT = None
KEEPALIVE_PORT = None

multicast_thread = None
unicast_thread = None
keepalive_thread = None
ping_client_thread = None


# File Descriptors (Sockets)
multicast_fd = None
unicast_fd = None
keepalive_fd = None
ping_client_socket_fd = None

@dataclass(frozen=True, order=True)
class Request:
    # Header
    request_sequence: int
    client_sequence: tuple
    client_address: tuple
    service: int

    # Payload
    buffer: str
    
    
    def __eq__(self, other):
        return (self.client_sequence    ==  other.client_sequence   and \
                self.client_address     ==  other.client_address    and \
                self.service            ==  other.service           and \
                self.buffer             ==  other.buffer)





# Register a unique service
def register(service):
    if service in services:
        return
    services.append(service)


# Unregister a service if it exists
def unregister(service):
    try:
        services.remove(service)
    except:
        return




def get_request(service):
    global LOAD
    for request in requests:
        if request.service != str (service):
            print(request.service)
            continue
        
        # Ping Client
        ping_client_thread = threading.Thread(target=ping_client, args=(request.client_address,))
        ping_client_thread.start()

        LOAD = LOAD + 1
        return request.request_sequence, request.buffer, len(request.buffer)


def send_reply(request_id, buffer, length):
    for request in requests[:]:
        if request_id != request.request_sequence:
            continue

        buffer = buffer[:length]

        unicast_fd.sendto(buffer.encode('ascii'), request.client_address)

        print(request)
        requests.remove(request)


def print_services():
    print(services)



def multicast_discovery():
    global multicast_fd

    multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_fd.bind((MULTICAST_GROUP, MULTICAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    while True:
        buffer, client = multicast_fd.recvfrom(REQUEST_LENGTH)
        service = int(buffer.decode()[:-1])
        
        print(int (service))
        if service not in services:
            response = 'NACK'
        else:
            response = 'ACK:{LOAD}:{SERVER_IP}:{UNICAST_PORT}:{KEEPALIVE_PORT}'.format(LOAD=LOAD, SERVER_IP=SERVER_IP, UNICAST_PORT=UNICAST_PORT, KEEPALIVE_PORT=KEEPALIVE_PORT)
            print(response)
        multicast_fd.sendto(response.encode(), client)


def unicast_communication():
    global REQUEST_SEQUENCE
    global unicast_fd
    unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    unicast_fd.bind((SERVER_IP, UNICAST_PORT))

    
    while True:
        data, client = unicast_fd.recvfrom(REQUEST_LENGTH) #ENABLE POLLING
        data = data.decode('ascii')
        if data != "PING":
            data = data.split(':')

            sequence = (data[0], client)
            service = data[1]
            buffer = data[2]
            request = Request(request_sequence=REQUEST_SEQUENCE, client_sequence=sequence, client_address=client, service=service, buffer=buffer)
            
            if request not in requests:
                requests.append(request)
                REQUEST_SEQUENCE = REQUEST_SEQUENCE + 1
            
        
        # Send acknowledgement back to client
        acknowledgement = "ACK"
        unicast_fd.sendto(acknowledgement.encode('ascii'), request.client_address)

def ping_client(client_address):
    global ping_client_socket_fd
    request = "PING"
    response = "ACK"

    ping_client_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ping_client_socket_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    inputs = [ping_client_socket_fd]
    outputs = [ping_client_socket_fd]

    TRIES = 4
    while True:
        readable, writable, errors = select.select(inputs, outputs, inputs, 1)

        ping_client_socket_fd.sendto(request.encode('ascii'), client_address)
        
        for ping_client_socket_fd in readable:
            data, client = ping_client_socket_fd.recvfrom(REQUEST_LENGTH)
            print(data)


    # print(client_address)

def keepalive_communication():
    global keepalive_fd

    keepalive_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    keepalive_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    keepalive_fd.bind((SERVER_IP, KEEPALIVE_PORT))

    #nonblock socket
    inputs = [keepalive_fd]
    outputs = [keepalive_fd]
    
    response = 'ACK'
    while inputs:
        readable, writable, errors = select.select(inputs, outputs, inputs, 1)
       
        # for keepalive_fd in writable:
        #     data = keepalive_fd.send("")
        #     outputs.remove(keepalive_fd)
        
        for keepalive_fd in readable:
            data, client = keepalive_fd.recvfrom(REQUEST_LENGTH)
            keepalive_fd.sendto(response.encode('ascii'), client)
    
        # for keepalive_fd in exceptional:
        #     inputs.remove(keepalive_fd)
        #     outputs.remove(keepalive_fd)
        #     break

    
    
    # while True:
    #     data, client = keepalive_fd.recvfrom(REQUEST_LENGTH)
    #     print(client)
    #     keepalive_fd.sendto(response.encode('ascii'), client)

    print('End')

def api_init():
    global SERVER_IP 
    global UNICAST_PORT
    global KEEPALIVE_PORT
    global multicast_thread
    global unicast_thread
    global keepalive_thread
    global LOAD #
    # if len(sys.argv) != 3:
    #     print("python3 <EXECUTABLE> <UNICAST IP> <UNICAST PORT>")
    #     exit(0)


    SERVER_IP = sys.argv[1]
    UNICAST_PORT = int (sys.argv[2])
    KEEPALIVE_PORT = int (sys.argv[3])
    LOAD = int (sys.argv[4]) #

    # Create Threads
    multicast_thread = threading.Thread(target=multicast_discovery)
    unicast_thread = threading.Thread(target=unicast_communication)
    #keepalive_thread = threading.Thread(target=keepalive_communication)

    # Start Threads
    multicast_thread.start()
    unicast_thread.start()
    #keepalive_thread.start()
    

def api_destroy():
    if multicast_thread:
        multicast_thread.join()
    if unicast_thread:
        unicast_thread.join()
    #if keepalive_thread:
     #   keepalive_thread.join()


api_init()