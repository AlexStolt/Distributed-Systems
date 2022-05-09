import threading
import time
import socket
import copy
import sys


SEPERATOR = '\0'

class Cache:
  def __init__(self, cache_blocks, block_size, fresh_t):
    self.cache_blocks = cache_blocks
    self.block_size = block_size
    self.fresh_t = fresh_t
    self.cache_mutex = threading.Lock()
    
    self.blocks = []

  def find_block(self, file_id: int, start: int):
    self.cache_mutex.acquire()  
    for block in self.blocks:
      if block.file_id != file_id or block.start != start:
        continue
      
      self.cache_mutex.release()
      return block
    
    self.cache_mutex.release()
    return None
    
  def insert_block(self, block):
    self.cache_mutex.acquire()
    block_index = -1
    freshness = sys.maxsize
    
    # LRU when Cache is Full
    if len(self.blocks) == self.cache_blocks:
      # Find Oldest Cached Block
      for i, cache_block in enumerate(self.blocks):
        if cache_block.t_fresh < freshness:
          block_index = i
          freshness = cache_block.t_fresh
      
      #  Remove Block from Cache
      if block_index != -1:
        self.blocks.pop(block_index)
        
    if len(self.blocks) != self.cache_blocks:
      self.blocks.append(block)
    
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
    
    start_position = start
    for _ in range(int((end - start) / self.block_size)):
      requested_blocks.append(Block(file_id, start=start_position, valid_block_size=-1, t_fresh=-1, data=''))
      start_position = start_position + self.block_size
    
    self.cache_mutex.acquire()
    for block in self.blocks:
      if block.file_id != file_id:
        continue
        
      if block.start < start or block.start + self.block_size > end:
        continue
      
      for block_index in range(len(requested_blocks)):
        if requested_blocks[block_index].start != block.start:
          continue
        requested_blocks[block_index] = copy.deepcopy(block)
    
    self.cache_mutex.release()
    return requested_blocks


  
class Block:
  def __init__(self, file_id, start, valid_block_size, t_fresh, data):
    self.file_id = file_id
    self.start = start
    self.valid_block_size = valid_block_size
    self.t_fresh = t_fresh
    self.t_modified = -1
    self.data = data
    
    # Variables that are True can be discarded by the LRU
    self.delivered_to_application = False
  
  def update_block(self, valid_block_size, t_fresh, t_modified, data):
    self.valid_block_size = valid_block_size
    self.t_fresh = t_fresh
    self. t_modified = t_modified
    self.data = data
  
  def reset_block(self):
    self.valid_block_size = -1 
    self.t_fresh = -1 
    self.t_modified = -1
    self.data = ''
  
  
  @property
  def is_valid(self):
    if self.valid_block_size < 0 or self.t_fresh < 0:
      return False
    return True
  
  @property
  def is_fresh(self):
    if time.time() > self.t_fresh:
      return False
    return True
  
  def __str__(self):
    return f'[file_id: {self.file_id} start: {self.start} valid_block_size: {self.valid_block_size} fresh_t: {self.t_fresh} t_modified: {self. t_modified} data: {self.data}]'


class Requests:
  sequence = 0
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


class SatisfiedRequests():
  def __init__(self):
    self.satisfied_read_requests    = []
    self.satisfied_lookup_requests  = []
    self.satisfied_write_requests   = []
    
    
    self.satisfied_read_requests_mutex    = threading.Lock()
    self.satisfied_lookup_requests_mutex  = threading.Lock()
    self.satisfied_write_requests_mutex   = threading.Lock()
    
    
  def insert_satisfied_lookup_request(self, request_sequence: int, status: bool):
    self.satisfied_lookup_requests_mutex.acquire()
    self.satisfied_lookup_requests.append(self.SatisfiedLookupRequest(request_sequence, status))
    self.satisfied_lookup_requests_mutex.release()
    

  def get_satisfied_lookup_request(self, request_sequence):
    self.satisfied_lookup_requests_mutex.acquire()
    for request in self.satisfied_lookup_requests:
      if request.request_sequence != request_sequence:
        continue
      
      self.satisfied_lookup_requests_mutex.release()
      return request
    
    self.satisfied_lookup_requests_mutex.release()
    return None
  
      
  def insert_satisfied_read_request(self, request_sequence: int, status: bool, blocks: list):
    self.satisfied_read_requests_mutex.acquire()
    self.satisfied_read_requests.append(self.SatisfiedReadRequest(request_sequence, status, blocks))
    self.satisfied_read_requests_mutex.release()
    
    
  def get_satisfied_read_request(self, request_sequence: int):
    self.satisfied_read_requests_mutex.acquire()
    for request in self.satisfied_read_requests:
      if request.request_sequence != request_sequence:
        continue
      
      self.satisfied_read_requests_mutex.release()
      return request
    
    self.satisfied_read_requests_mutex.release()
    return None
  
  
  def insert_satisfied_write_request(self, request_sequence, status: bool, bytes_written: int):
    self.satisfied_write_requests_mutex.acquire()
    self.satisfied_write_requests.append(self.SatisfiedWriteRequest(request_sequence, status, bytes_written))
    self.satisfied_write_requests_mutex.release()
  
  
  def get_satisfied_write_request(self, request_sequence: int):
    self.satisfied_write_requests_mutex.acquire()
    for request in self.satisfied_write_requests:
      if request.request_sequence != request_sequence:
        continue
      
      self.satisfied_write_requests_mutex.release()
      return request
    
    self.satisfied_write_requests_mutex.release()
    return None
  
  
  
  class SatisfiedLookupRequest:
    def __init__(self, request_sequence: int, status: bool):
      self.request_sequence = request_sequence
      self.status = status
  
  
  class SatisfiedReadRequest:
    def __init__(self, request_sequence, status, blocks):
      self.request_sequence = request_sequence
      self.status = status
      self.blocks = blocks
    
    def get_data(self, position: int, length: int):
      data = ''
      
      for i, block in enumerate(self.blocks):
        if not i:
          start = position - block.start
          end = start + min(length - len(data), block.valid_block_size)
          
          data = block.data[start:end]
        elif i != len(self.blocks) - 1:
          data = data + block.data
        else:
          data = data + block.data[:min(length - len(data), block.valid_block_size)]
      
      return data, len(data)
      
    def __str__(self):
      return f'Sequence: {self.request_sequence}, Blocks: {self.blocks}'


  class SatisfiedWriteRequest:
    def __init__(self, request_sequence, status, bytes_written):
      self.request_sequence = request_sequence
      self.status = status
      self.bytes_written = bytes_written

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
    self.sequence_mutex = threading.Lock()
    self.request_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Increment Sequence Number
    self.sequence_mutex.acquire()
    self.sequence = Requests.sequence
    Requests.sequence = Requests.sequence + 1
    self.sequence_mutex.release()
        
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
    self.reincarnation_count = 0
    self.files_mutex = threading.Lock()

# Append a File to the Files Container
  def append_file(self, file_path: str, file_id: int, reincarnation_number: int):
    self.files_mutex.acquire()

    # Used when handling lookup locally
    if self.reincarnation_count < reincarnation_number:
      self.reincarnation_count = reincarnation_number

    for file in self.files:
      if file.file_id != file_id:
        continue
      
      # ID Already Exists
      file.add_fd(self.fd_count, reincarnation_number)
      self.fd_count = self.fd_count + 1
      
      self.files_mutex.release()
      return
    
    # ID Does Not Exist
    self.files.append(self.File(
      file_path = file_path,
      file_id = file_id,
      file_fd = self.fd_count,
      reincarnation_number=reincarnation_number
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
        if fd['position'] < 0:
          fd['position'] = 0
          
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

  def update_position_by_fd(self, file, fd, position):
    self.files_mutex.acquire()
    if file.update_position(fd, position):
      self.files_mutex.release()
      return True
    
    self.files_mutex.release()
    return False


  class File:
    file_fds = []
    def __init__(self, file_path, file_id, file_fd, reincarnation_number):
      self.file_path = file_path
      self.file_id = file_id
      self.file_fds.append({
        'fd': file_fd,
        'reincarnation_number': reincarnation_number,
        'position': -1
      })

    def add_fd(self, file_fd, reincarnation_number):
      self.file_fds.append({
        'fd': file_fd,
        'reincarnation_number': reincarnation_number,
        'position': -1
      })

    def contains(self, file_fd):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return True
      return False

    def fd_index(self, file_fd: int):
      for i, fd in enumerate(self.file_fds):
        if fd['fd'] != file_fd:
          continue
        return i
      return -1

    def get_position(self, file_fd: int):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return fd['position']
      return -1

    def get_reincarnation_number(self, file_fd: int):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        return fd['reincarnation_number']
      return -1

    def update_position(self, file_fd: int, position: int):
      for fd in self.file_fds:
        if fd['fd'] != file_fd:
          continue
        fd['position'] = position
        return True
      return False