from concurrent.futures import thread
from ctypes.wintypes import SIZE
import random
import socket
import threading
import time
import sys
from collections import deque
from enum import Enum


# File Operations
O_RDONLY  =   0
O_WRONLY  =   1
O_RDWR    =   2
O_CREAT   =   100
O_EXCL    =   200
O_TRUNC   =   1000


PACKET_LENGTH = 1024
SEPERATOR = b"1010AAAA1010"

class Cache:
  def __init__(self, cache_blocks, block_size, fresh_t):
    self.cache_blocks = cache_blocks
    self.block_size = block_size
    self.fresh_t = fresh_t

    blocks = []

  def insert_block():
    pass


  class Block:
    def __init__(self, start, block_size, t_fresh, t_modified, data):
      pass


class Requests:
  def __init__(self):
    self.pending_requests = []
    self.pending_requests_semaphore = threading.Semaphore(0)
    self.pending_requests_mutex = threading.Lock()

  def insert_request(self, payload):
    self.pending_requests_mutex.acquire()
    
    # Append Request to List
    self.pending_requests.append(self.Request(payload))
    
    self.pending_requests_semaphore.release()
    self.pending_requests_mutex.release()

    # Block Application till Request Satisfied
    self.pending_requests[-1].block_application_semaphore.acquire()


  class Request:
    def __init__(self, payload):
      self.payload = payload
      self.block_application_semaphore = threading.Semaphore(0)



class Files:
  def __init__(self):
    self.files = []
    self.fd_count = 0
    self.files_mutex = threading.Lock()


  def append_file(self, file_path, file_id):
    self.files_mutex.acquire()

    for file in self.files:
      if file.file_id != file_id:
        continue
      
      # ID Already Exists
      file.add_fd(self.fd_count)
      self.fd_count = self.fd_count + 1
      
      self.files_mutex.release()
      return
    
    # ID Does Not Exist
    self.files.append(self.File(
      file_path = file_path,
      file_id = file_id,
      file_fd = self.fd_count
    ))

    self.fd_count = self.fd_count + 1

    self.files_mutex.release()

  # Return FD Based on File Path
  def get_fd(self, file_path):
    self.files_mutex.acquire()
    for file in self.files:
      if file.file_path != file_path:
        continue 
      
      for fd in file.file_fds:
        if fd['position'] < 0:
          fd['position'] = 0
          
          self.files_mutex.release()
          return fd['fd']

    self.files_mutex.release()
    return -1

  # Return ID Based on FD
  def get_id(self, file_fd):
    self.files_mutex.acquire()
    for file in self.files:
      if not file.contains(file_fd):
        continue

      self.files_mutex.release()
      return file.file_id

    self.files_mutex.release()
    return -1



  class File:
    file_fds = []
    def __init__(self, file_path, file_id, file_fd):
      self.file_path = file_path
      self.file_id = file_id
      self.file_fds.append({
        'fd': file_fd,
        'position': -1
      })

    def add_fd(self, file_fd):
      self.file_fds.append({
        'fd': file_fd,
        'position': -1
      })

    def contains(self, file_fd):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return True
      return False


SERVER_IP = None
SERVER_PORT = None
udp_unicast_fd = None
files_container = None
requests_container = None








def requests_handler():
  while True:
    requests_container.pending_requests_semaphore.acquire()
    requests_container.pending_requests_mutex.acquire()
    
    # Get Request
    selected_request = requests_container.pending_requests.pop(0)

    requests_container.pending_requests_mutex.release()

    # Handle Request
    udp_unicast_fd.sendto(selected_request.payload.encode(), (SERVER_IP, SERVER_PORT))
    
    response, server_address = udp_unicast_fd.recvfrom(PACKET_LENGTH)
    response = response.split(SEPERATOR)

    # Handle Lookup Requests
    if response[0] == b'LOOKUP_RES':
      if response[1] != b'ACK':
        continue
      files_container.append_file(response[2].decode(), int(response[3].decode()))
    else:
      pass


    # Unblock Application
    selected_request.block_application_semaphore.release()
    







def nfs_init(server_ip, server_port, cache_blocks, block_size, fresh_t):
  global SERVER_IP
  global SERVER_PORT
  global files_container
  global requests_container
  global udp_unicast_fd

  SERVER_IP = server_ip
  SERVER_PORT = server_port
  requests_container = Requests()
  files_container = Files()


  udp_unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  
  request_handler_thread = threading.Thread(target=requests_handler)
  request_handler_thread.start()




def nfs_open(path, flags):
  payload = f'LOOKUP_REQ:{flags}:{path}'
  requests_container.insert_request(payload)
  return files_container.get_fd(path)
  




def nfs_read(fd, buffer, length):
  pass


def nfs_write(fd, buffer, length):
  pass

def nfs_seek(fd, position, whence):
  pass


def nfs_ftruncate(fd, length):
  pass


def nfs_close(fd):
  pass 