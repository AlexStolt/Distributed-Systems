import threading
import time
import socket
import copy


SEPERATOR = '\0'

class Cache:
  def __init__(self, cache_blocks, block_size, fresh_t):
    self.cache_blocks = cache_blocks
    self.block_size = block_size
    self.fresh_t = fresh_t
    self.cache_mutex = threading.Lock()
    
    self.blocks = []

  def insert_block(self, start, valid_size, data):
    self.cache_mutex.acquire()
    self.blocks.append(self.Block(start=start, valid_size=valid_size, t_fresh=time.time(), data=data))
    self.cache_mutex.release()
    
  def get_blocks(self, file_id: int, position: int, length: int):
    requested_blocks = []
    
    # Start of Block
    start = position
    while start % self.block_size:
      start = start - 1
    
    # End of Block
    end = position + length
    while end % self.block_size:
      end = end + 1
    
    for _ in range(int((end - start) / self.block_size)):
      requested_blocks.append(None)
    
    self.cache_mutex.acquire()
    for block in self.blocks:
      if block.file_id != file_id:
        continue
        
      if block.start < start or block.start + self.block_size > end:
        continue
      
      requested_blocks[block.start / self.block_size] = copy.deepcopy(block)
    
    self.cache_mutex.release()
    return requested_blocks


  def check_block_state(self, block):
    return True
  
  
  class Block:
    def __init__(self, file_id, start, valid_block_size, t_fresh, data):
      self.file_id = file_id
      self.start = start
      self.valid_block_size = valid_block_size
      self.t_fresh = t_fresh
      self. t_modified = -1
      self.data = data
      
      # Variables that are True can be discarded by the LRU
      self.delivered_to_application = False
    
    def update_block():
      pass


class Requests:
  def __init__(self):
    self.pending_requests = []
    self.pending_requests_semaphore = threading.Semaphore(0)
    self.pending_requests_mutex = threading.Lock()

  def insert_request(self, request):
    self.pending_requests_mutex.acquire()
    
    # Append Request to List
    self.pending_requests.append(request)
    
    self.pending_requests_semaphore.release()
    self.pending_requests_mutex.release()

    # Block Application till Request Satisfied
    self.pending_requests[-1].block_application_semaphore.acquire()


class Request:
  def __init__(self, *fields):
    self.request = ''
    for field in fields:
      field_to_str = str(field)
      self.request += str(len(field_to_str)) + SEPERATOR + field_to_str
    self.request = str(len(self.request)) + SEPERATOR + self.request 
    
    self.fields = fields
    self.request = self.request.encode()
    self.block_application_semaphore = threading.Semaphore(0)
    self.request_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
  # Parse an encoded request string to its multiple fields
  @staticmethod
  def parse_request(encoded_request: str):
    fields = []
  
    encoded_request = encoded_request[encoded_request.find(b'\x00') + 1:]
    decoded_request = encoded_request.decode()
    
    i = 0
    while i < len(decoded_request):
      # Get Length
      len_str = '' 
      while decoded_request[i] != '\x00':
        len_str = len_str + decoded_request[i]
        i = i + 1
      
      # Get Data
      field = ''
      for j in range(int(len_str)):
        field = field + decoded_request[i + j + 1]
      
      fields.append(field.encode())
      i = i + int(len_str) + 1
    
    return fields


class Files:
  def __init__(self):
    self.files = []
    self.fd_count = 0
    self.files_mutex = threading.Lock()

# Append a File to the Files Container
  def append_file(self, file_path: str, file_id: int):
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
  def get_fd_from_path(self, file_path):
    self.files_mutex.acquire()
    for file in self.files:
      if file.file_path != file_path:
        continue 
      
      for fd in file.file_fds:
        if fd['fp_position'] < 0:
          fd['fp_position'] = 0
          
          self.files_mutex.release()
          return fd['fd']
    
    self.files_mutex.release()
    return -1


  # Return ID Based on FD
  def get_id_from_fd(self, file_fd: int):
    self.files_mutex.acquire()
    for file in self.files:
      if not file.contains(file_fd):
        continue

      self.files_mutex.release()
      return file.file_id

    self.files_mutex.release()
    return -1


  # Return a File from its FD
  def get_file_from_fd(self, file_fd: int):
    self.files_mutex.acquire()
    for file in self.files:
      if not file.contains(file_fd):
        continue

      self.files_mutex.release()
      return file

    self.files_mutex.release()
    return None


  # Return a File from its ID
  def get_file_from_id(self, file_id):
    self.files_mutex.acquire()
    for file in self.files:
      if file.file_id != file_id:
        continue
      
      self.files_mutex.release()
      return file
    
    self.files_mutex.release()
    return None
  
  
  # Search Files by Path
  def get_file_by_path(self, file_path):
    self.files_mutex.acquire()
    for file in self.files:
      if file.file_path != file_path:
        continue
      
      self.files_mutex.release()
      return file
    
    self.files_mutex.release()
    return None


  class File:
    file_fds = []
    def __init__(self, file_path, file_id, file_fd):
      self.file_path = file_path
      self.file_id = file_id
      self.file_fds.append({
        'fd': file_fd,
        'fp_position': -1
      })

    def add_fd(self, file_fd):
      self.file_fds.append({
        'fd': file_fd,
        'fp_position': -1
      })

    def contains(self, file_fd):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return True
      return False

    def get_position(self, file_fd: int):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return fd['fp_position']
      return -1