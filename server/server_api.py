from locale import atoi
from ntpath import join
import os
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
import binascii
from simplejson import load
import ast
ENABLE_BACKUP = True

requests_list_mutex = threading.Lock()
load_mutex = threading.Lock()
file_mutex = threading.Lock()

# Global Variables
services = []
requests  = []


TIMEOUT = 1
TRIES = 4
REQUEST_LENGTH = 1024
LOAD = 0
REQUEST_SEQUENCE = 0

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 8000




multicast_thread = None
unicast_thread = None

BACKUP_FILE = None
BACKUP_SOCKET = False

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

    def activate_processing(self):
        self.processing = True

    
    def __eq__(self, other):
        return (self.client_sequence    ==  other.client_sequence   and \
                self.client_address     ==  other.client_address    and \
                self.service            ==  other.service           and \
                self.buffer             ==  other.buffer)
    


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

def backup_delete_request(request):
    file_mutex.acquire()
    delete_request_data = f'{request.request_sequence}:{request.client_sequence}:{request.client_address}:{request.service}:{request.buffer}'
    
    with open(BACKUP_FILE, "r") as file:
        lines = file.readlines()
        print(f"\n-----------\n{lines}\n{delete_request_data}\n-----------\n")
    
    if lines:
        with open(BACKUP_FILE, "w+") as file:
            for line in lines:
                if line.strip("\n") != delete_request_data:
                    file.write(line)

    file_mutex.release()

def get_request(service):
    global LOAD

    requests_list_mutex.acquire()
    for request in requests:
        if request.service != service or request.processing:
            continue
        
        request.flags.set_join(False)
        request.flags.set_abort(False)
        request.processing = True

        # print(requests)
        # exit(1)
        # Server Might Have Failed and Client Aborted
        # if ENABLE_BACKUP:
            
        #     requests_list_mutex.release()
        #     # ping_client(request.client_address, False, request.flags)
        #     requests_list_mutex.acquire()

        #     if request.flags.get_abort():
        #         print("\033[91m[ERROR]: Client", request.client_address, " Died and the Request is Cancelled\033[0;0m")
        #         print(request.client_address)
                
        #         # Item should be deleted from request list and backup file
        #         requests.remove(request)
        #         backup_delete_request(request)
        #         continue
        
        # Ping Client
        request.ping_client_thread = threading.Thread(target=ping_client, args=(request.client_address, True, request.flags, TRIES, ))
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
    global BACKUP_SOCKET

    requests_list_mutex.acquire()
    for request in requests[:]:
        if request_id != request.request_sequence:
            continue
        # print(request_id)
        buffer = buffer[:length]

        if not request.flags.get_abort():
            unicast_fd.sendto(buffer.encode('ascii'), request.client_address)
            if ENABLE_BACKUP:
                print("Delete Fuck: ", request) 
                backup_delete_request(request)
        else:
            print("\033[91m[ERROR] Client",request.client_address , "did not Respond\033[0;0m")

        

        request.flags.set_join(True)
        request.ping_client_thread.join()

        load_mutex.acquire()
        LOAD = LOAD - 1
        load_mutex.release()

        # Delete Request from List and File
        #requests.remove(request)
        
                

    requests_list_mutex.release()

def print_services():
    print(services)



def multicast_discovery():
    global multicast_fd
    global unicast_fd
    global BACKUP_SOCKET

    while True:
        buffer, client = multicast_fd.recvfrom(REQUEST_LENGTH)
        service = int(buffer.decode()[:-1])
        
        if service not in services:
            response = 'NACK'
        else:
            load_mutex.acquire()
            response = 'ACK:{LOAD}'.format(LOAD=LOAD)
            load_mutex.release()
    
        unicast_fd.sendto(response.encode(), client)
        if BACKUP_SOCKET:
            line = f'127.0.0.1:{unicast_fd.getsockname()[1]}\n'
            if ENABLE_BACKUP:
                file_mutex.acquire()
                with open(BACKUP_FILE, 'w+') as file:
                    content = file.read()
                    file.seek(0, 0)
                    file.write(line.rstrip('\r\n') + '\n' + content)
                BACKUP_SOCKET = False
                file_mutex.release()


def unicast_communication():
    global REQUEST_SEQUENCE
    global unicast_fd
    global BACKUP_FILE
    global ENABLE_BACKUP

    while True:
        readable, writable, errors = select.select([unicast_fd], [], [], TIMEOUT)
        
        for socket in readable:
            data, client = socket.recvfrom(REQUEST_LENGTH)
            #data = data.decode('ascii')
            data = data.split(b':')
            
            
            if data[0] != b'PING':
                requests_list_mutex.acquire()
                sequence = (int.from_bytes(data[0], "big"), client)
                service = int.from_bytes(data[1], "big")
                buffer = data[2]

                
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
                
                request_in_requests = False
                for request_iterator in requests:    
                    if request_iterator.client_sequence != request.client_sequence:
                        continue
                    request_in_requests = True
                
                if not request_in_requests:
                    requests.append(request)
                    
                    if ENABLE_BACKUP:
                        file_mutex.acquire()
                        # Write Request to File
                        with open(BACKUP_FILE, "a+") as file:
                            file.writelines(f'{REQUEST_SEQUENCE}:{sequence}:{client}:{service}:{buffer}\n')
                        file_mutex.release()
                
                    REQUEST_SEQUENCE = REQUEST_SEQUENCE + 1

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
            
def ping_client(client_address, repeat, flags, tries):
    global ping_client_socket_fd
    request = "PING"

    i = 0
    while i < tries:
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
    global REQUEST_SEQUENCE
    global BACKUP_FILE
    global BACKUP_SOCKET
    global multicast_thread
    global unicast_thread
    global multicast_fd
    global unicast_fd
    global ping_client_socket_fd
    global requests

    if len(sys.argv) != 2:
        print("python3 <EXECUTABLE> <BACKUP FILE>")
        exit(-1)


    BACKUP_FILE = sys.argv[1]

    # Multicast Socket
    multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_fd.bind((MULTICAST_GROUP, MULTICAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Unicast Socket
    unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if ENABLE_BACKUP:
        try:
            if os.stat(BACKUP_FILE).st_size != 0:
                with open(BACKUP_FILE, "r") as file:
                    address = file.readline()
                    address = address.split(':')
                    unicast_address = (address[0], int (address[1].replace('\n', '')))
                    # Server has failed so previously used port must be used
                    unicast_fd.bind(unicast_address)

                    # Server reads pending requests
                    lines = file.readlines()
                    
                    for line in lines:
                        fields = line.split(':')
                        largest_sequence = int (lines[-1].split(':')[0])
                        REQUEST_SEQUENCE = largest_sequence + 1
        
                        request = Request(
                            request_sequence = int(fields[0]), 
                            client_sequence = eval(fields[1]), 
                            client_address = eval(fields[2]), 
                            service = int (fields[3]), 
                            processing = False, 
                            ping_client_thread = None,
                            buffer = ast.literal_eval(fields[4]),
                            flags = Flags(False, False)
                        )
                        
                        if request not in requests:
                            # Append Request 
                            requests.append(request)

            else:
                BACKUP_SOCKET = True
        except:
            BACKUP_SOCKET = True

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