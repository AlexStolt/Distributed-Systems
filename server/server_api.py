from locale import atoi
from ntpath import join
from os import abort, pread
from colorama import Fore, Back, Style
import socket
from sre_parse import State
import struct
import threading
import time
import sys
import select
from typing import Any
from dataclasses import dataclass
import pickle

from simplejson import load

ENABLE_BACKUP = False

requests_list_mutex = threading.Lock()
load_mutex = threading.Lock()

# Global Variables
services = []
requests  = []


TIMEOUT = 1
TRIES = 10
REQUEST_LENGTH = 1024
LOAD = 0
REQUEST_SEQUENCE = 0

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 8000

SERVER_IP = None
UNICAST_PORT = None

multicast_thread = None
unicast_thread = None


# File Descriptors (Sockets)
multicast_fd = None
unicast_fd = None
ping_client_socket_fd = None

@dataclass(frozen=False, order=True)
class Request:
    # Header
    request_sequence: int
    client_sequence: tuple
    client_address: tuple
    service: int
    processing: bool

    # Payload
    buffer: str
    
    # Threading Related Information
    ping_client_thread: Any
    flags: Any

    
    def __eq__(self, other):
        return (self.client_sequence    ==  other.client_sequence   and \
                self.client_address     ==  other.client_address    and \
                self.service            ==  other.service           and \
                self.buffer             ==  other.buffer)
    
    def __ne__(self, other):
        return (self.client_sequence    !=  other.client_sequence   and \
                self.client_address     !=  other.client_address    and \
                self.service            !=  other.service           and \
                self.buffer             !=  other.buffer)


class Flags:
    def __init__(self, abort = False, join = False):
        self.abort = abort
        self.join = join

    def get_abort(self):
        return self.abort

    def set_abort(self, abort):
        self.abort = abort

    def get_join(self):
        return self.join

    def set_join(self, join):
        self.join = join


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

    requests_list_mutex.acquire()
    for request in requests:
        if request.service != service or request.processing:
            continue
        
        request.flags.set_join(False)
        request.flags.set_abort(False)
        
        request.processing = True
        
        # Server Might Have Failed and Client Aborted
        if ENABLE_BACKUP:
            ping_client(request.client_address, False)
            if request.flags.get_abort():
                print("\033[91m[ERROR]: Client", request.client_address, " Died and the Request is Cancelled\033[0;0m")
                print(request.client_address)
                # Item should be deleted here 
                continue
        
        # Ping Client
        request.ping_client_thread = threading.Thread(target=ping_client, args=(request.client_address, True, request.flags, ))
        request.ping_client_thread.start()

        load_mutex.acquire()
        LOAD = LOAD + 1
        load_mutex.release()

        requests_list_mutex.release()
        
        return request.request_sequence, request.buffer, len(request.buffer), request.flags
    
    requests_list_mutex.release()
    return -1, [], -1, None


def send_reply(request_id, buffer, length):
    global LOAD

    requests_list_mutex.acquire()
    for request in requests[:]:
        if request_id != request.request_sequence:
            continue

        buffer = buffer[:length]

        
        if not request.flags.get_abort():
            unicast_fd.sendto(buffer.encode('ascii'), request.client_address)
        else:
            print("\033[91m[ERROR] Client",request.client_address , "did not respond\033[0;0m")

        request.flags.set_join(True)
        request.ping_client_thread.join()

        load_mutex.acquire()
        LOAD = LOAD - 1
        load_mutex.release()

        requests.remove(request)
    requests_list_mutex.release()

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
            load_mutex.acquire()
            response = 'ACK:{LOAD}:{SERVER_IP}:{UNICAST_PORT}'.format(LOAD=LOAD, SERVER_IP=SERVER_IP, UNICAST_PORT=UNICAST_PORT)
            load_mutex.release()
    
        multicast_fd.sendto(response.encode(), client)


def unicast_communication():
    global REQUEST_SEQUENCE
    global unicast_fd
    
    while True:
        readable, writable, errors = select.select([unicast_fd], [], [], TIMEOUT)

        for socket in readable:
            data, client = socket.recvfrom(REQUEST_LENGTH)
            data = data.decode('ascii')
            data = data.split(':')
            
            if data[0] != "PING":
                sequence = (int.from_bytes(str.encode(data[0]), "big"), client)
                service = int.from_bytes(str.encode(data[1]), "big")
                buffer = str (data[2]).encode('ascii')
                
                request = Request(
                    request_sequence = REQUEST_SEQUENCE, 
                    client_sequence = sequence, 
                    client_address = client, 
                    service = service, 
                    processing = False, 
                    ping_client_thread = None,
                    buffer = buffer,
                    flags = Flags(False, False)
                )
                
                requests_list_mutex.acquire()
                print(sequence)
                print("HEllo")
                if request not in requests: # This part fails
                    requests.append(request)
                    REQUEST_SEQUENCE = REQUEST_SEQUENCE + 1

                    if ENABLE_BACKUP:
                        # Write List of Requests to File
                        backup_file = "{FILE_NAME}.bckp".format(FILE_NAME=UNICAST_PORT)
                        with open(backup_file, "wb") as file:
                            pickle.dump(requests, file)
                
                requests_list_mutex.release()
                response = "ACK"
            else:
                service_id = int(data[1])
                if service_id not in services:
                    response = "NACK"
                else:
                    response = "ACK"

            # Send acknowledgement back to client
            socket.sendto(response.encode('ascii'), client)
            
def ping_client(client_address, repeat, flags):
    global ping_client_socket_fd
    request = "PING"

    i = 0
    while i < TRIES:
        if flags.get_join():
            return

        ping_client_socket_fd.sendto(request.encode('ascii'), client_address)
        
        readable, writable, errors = select.select([ping_client_socket_fd], [], [], TIMEOUT)

        for socket in readable:
            try:
                data, client = socket.recvfrom(REQUEST_LENGTH)
            except:
                break
            data = data.decode('ascii')
            
            if data and data == "ACK":
                if not repeat:
                    return
                i = 0
                break

        i = i + 1

    # Client Aborted (Notify Application with this Flag)
    flags.set_abort(True)




def api_init():
    global SERVER_IP 
    global UNICAST_PORT
    global multicast_thread
    global unicast_thread
    global multicast_fd
    global unicast_fd
    global ping_client_socket_fd
    global requests

    if len(sys.argv) != 3:
        print("python3 <EXECUTABLE> <UNICAST IP> <UNICAST PORT>")
        exit(0)


    SERVER_IP = sys.argv[1]
    UNICAST_PORT = int (sys.argv[2])

    if ENABLE_BACKUP:
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
    unicast_fd.setblocking(False)

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