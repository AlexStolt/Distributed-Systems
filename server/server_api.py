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
import pickle

# Global Variables
services = []
requests  = []

ABORT_PING_CLIENT = False
JOIN_PING_CLIENT = False

TIMEOUT = 1
TRIES = 4
REQUEST_LENGTH = 1024
LOAD = 0
REQUEST_SEQUENCE = 0

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 8000

SERVER_IP = None
UNICAST_PORT = None

multicast_thread = None
unicast_thread = None
ping_client_thread = None


# File Descriptors (Sockets)
multicast_fd = None
unicast_fd = None
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
    global ping_client_thread
    global JOIN_PING_CLIENT 
    global ABORT_PING_CLIENT
    global LOAD

    JOIN_PING_CLIENT = False
    ABORT_PING_CLIENT = False

    for request in requests:
        ABORT_PING_CLIENT = False
        if request.service != str (service):
            continue
        
        # Server Might Have Failed and Client Aborted
        print(request)
        ping_client(request.client_address, False)
        if ABORT_PING_CLIENT:
            print("Client Died and the Request is Cancelled")
            # Item should be deleted here 




            
            continue
        
        # Ping Client
        ABORT_PING_CLIENT = False
        ping_client_thread = threading.Thread(target=ping_client, args=(request.client_address, True, ))
        ping_client_thread.start()

        LOAD = LOAD + 1
        return request.request_sequence, request.buffer, len(request.buffer)
    return -1, [], -1


def send_reply(request_id, buffer, length):
    global JOIN_PING_CLIENT
    global ping_client_thread

    for request in requests[:]:
        if request_id != request.request_sequence:
            continue

        buffer = buffer[:length]

        if not ABORT_PING_CLIENT:
            unicast_fd.sendto(buffer.encode('ascii'), request.client_address)
        
        JOIN_PING_CLIENT = True
        ping_client_thread.join()

        print(request)
        requests.remove(request)


def print_services():
    print(services)



def multicast_discovery():
    global multicast_fd

    while True:
        buffer, client = multicast_fd.recvfrom(REQUEST_LENGTH)
        service = int(buffer.decode()[:-1])
        
        if service not in services:
            response = 'NACK'
        else:
            response = 'ACK:{LOAD}:{SERVER_IP}:{UNICAST_PORT}'.format(LOAD=LOAD, SERVER_IP=SERVER_IP, UNICAST_PORT=UNICAST_PORT)
            print(response)
        multicast_fd.sendto(response.encode(), client)


def unicast_communication():
    global REQUEST_SEQUENCE
    global unicast_fd
    
    while True:
        data, client = unicast_fd.recvfrom(REQUEST_LENGTH) #ENABLE POLLING to kill thread
        data = data.decode('ascii')
        data = data.split(':')

        if data[0] != "PING":
            sequence = (data[0], client)
            service = data[1]
            buffer = data[2]
            request = Request(request_sequence=REQUEST_SEQUENCE, client_sequence=sequence, client_address=client, service=service, buffer=buffer)
        
            if request not in requests:
                requests.append(request)
                REQUEST_SEQUENCE = REQUEST_SEQUENCE + 1
            
                # Write List of Requests to File
                backup_file = "{FILE_NAME}.bckp".format(FILE_NAME=UNICAST_PORT)
                with open(backup_file, "wb") as file:
                    pickle.dump(requests, file)

            response = "ACK"
        else:
            service_id = int(data[1])
            if service_id not in services:
                response = "NACK"
            else:
                response = "ACK"

        # Send acknowledgement back to client
        unicast_fd.sendto(response.encode('ascii'), client)

def ping_client(client_address, repeat):
    global ABORT_PING_CLIENT
    global ping_client_socket_fd
    request = "PING"

    i = 0
    while i < TRIES:
        if JOIN_PING_CLIENT:
            return

        ping_client_socket_fd.sendto(request.encode('ascii'), client_address)
        
        readable, writable, errors = select.select([ping_client_socket_fd], [], [], TIMEOUT)

        for socket in readable:
            data, client = socket.recvfrom(REQUEST_LENGTH)
            data = data.decode('ascii')
            if data == "ACK":
                if not repeat:
                    return
                i = 0
                break
        
        i = i + 1

    # Client Aborted (Notify Application with this Flag)
    ABORT_PING_CLIENT = True




def api_init():
    global SERVER_IP 
    global UNICAST_PORT
    global multicast_thread
    global unicast_thread
    global LOAD #
    global multicast_fd
    global unicast_fd
    global ping_client_socket_fd
    global requests

    # if len(sys.argv) != 3:
    #     print("python3 <EXECUTABLE> <UNICAST IP> <UNICAST PORT>")
    #     exit(0)


    SERVER_IP = sys.argv[1]
    UNICAST_PORT = int (sys.argv[2])
    LOAD = int (sys.argv[3]) #

    try:
        backup_file = "{FILE_NAME}.bckp".format(FILE_NAME=UNICAST_PORT)
        with open(backup_file, "rb") as file:
            requests =  pickle.load(file)
            print(requests)
    except:
        pass

    # Multicast Socket
    multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_fd.bind((MULTICAST_GROUP, MULTICAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Unicast Socket
    unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    unicast_fd.bind((SERVER_IP, UNICAST_PORT))

    # Keepalive Socket
    ping_client_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ping_client_socket_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ping_client_socket_fd.setblocking(False)

    # Create Threads
    multicast_thread = threading.Thread(target=multicast_discovery)
    unicast_thread = threading.Thread(target=unicast_communication)

    # Start Threads
    multicast_thread.start()
    unicast_thread.start()
    

def api_destroy():
    if multicast_thread:
        multicast_thread.join()
    if unicast_thread:
        unicast_thread.join()


api_init()