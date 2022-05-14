from math import remainder
from turtle import position
from classes import *


# Whence Identifiers
SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2
EOF = -1


THREADS = 4

PACKET_LENGTH = 1024

SERVER_IP = None
SERVER_PORT = None
udp_unicast_fd = None
files_container = None
requests_container = None
cache = None
satisfied_requests = None
DEBUG = True

def handle_lookup_locally(selected_request):
  request_fields = selected_request.fields
  header, file_path, flags = request_fields
  
  # Check Locally if File Already Exists with the same Permissions
  files_container.files_mutex.acquire()
  selected_file = None
  for file in files_container.files:
    for fd in file.file_fds:
      if fd['flags'] & flags != flags:
        continue
      
      selected_file = file
      break
  files_container.files_mutex.release()
  
  if not selected_file:
    return False
  
  # Append FD
  files_container.append_file(selected_file.file_path, selected_file.file_path, files_container.reincarnation_count, flags)
  return True


def handle_lookup(selected_request):
  request_fields = selected_request.fields
  header, file_path, flags = request_fields
  
  # Try to Satisfy Request without Contacting the Server
  if handle_lookup_locally(selected_request):
    # Notify that the Request was Successfull and Unblock Application
    satisfied_requests.insert_satisfied_lookup_request(request_sequence=selected_request.sequence, status=True)
    selected_request.block_application_semaphore.release()
    return
  
  # Send Request to Server
  selected_request.request_socket_fd.sendto(selected_request.request, (SERVER_IP, SERVER_PORT))
  
  
  # Wait for the Respose
  response, _ = selected_request.request_socket_fd.recvfrom(PACKET_LENGTH)
  response_fields = Request.parse_request(response)

  # Handle Lookup Requests
  try:
    response_type, status, file_path, file_id, reincarnation_number = response_fields 
  except:
    response_type, status = response_fields
  
  if status != b'ACK':
    # Notify that the Request was not Successfull and Unblock Application
    satisfied_requests.insert_satisfied_lookup_request(request_sequence=selected_request.sequence, status=False)
    selected_request.block_application_semaphore.release()
    return
  
  # Append File
  files_container.append_file(file_path.decode(), int(file_id.decode()), int(reincarnation_number.decode()), flags)
  
  # Notify that the Request was Successfull and Unblock Application
  satisfied_requests.insert_satisfied_lookup_request(request_sequence=selected_request.sequence, status=True)
  selected_request.block_application_semaphore.release()


def handle_read(selected_request):
  request_type, file_id, reincarnation_number, block_size, fp_position, length = selected_request.fields  
  
  # Get Blocks from Cache
  cached_blocks = cache.get_blocks(file_id, fp_position, length)
  
  # Request Missing Blocks or Blocks that have Expired
  for block in cached_blocks:
    # Cache Block was Removed by the LRU and must be Reset
    if not cache.find_block(block.file_id, block.start):
      block.reset_block()
    
    # Check if Block is Valid (If Block is Valid the Block is in Cache) and if Block is Fresh 
    if (not block.is_valid) or (block.is_valid and not block.is_fresh):
      
      # Cache Miss
      if not block.is_valid:
        if DEBUG:
          print(f"\033[91mCache Miss: [{block.start}, {block.start + block_size}]\033[00m")
      
      # Cache Block Expiration
      elif block.is_valid and not block.is_fresh:
        if DEBUG:
          print(f"\033[93mExpired Block: [{block.start}, {block.start + block_size}]\033[00m")
      
      
      # Create the Request
      request = Request(request_type, file_id, reincarnation_number, block.start, block_size, block.t_modified)
      
      # Send Request to Server
      request.request_socket_fd.sendto(request.request, (SERVER_IP, SERVER_PORT))
    
      # Wait for the Respose
      response, _ = request.request_socket_fd.recvfrom(PACKET_LENGTH)
      response_fields = Request.parse_request(response)
      
      # ACK and Data
      if len(response_fields) == 4:
        # Block was Refreshed
        response_type, status, t_modified, data = response_fields 
        
        # Modified Block
        block.valid_block_size = len(data)
        block.t_modified = int(t_modified)
        block.data = data

        if DEBUG:
          if block.is_valid and not block.is_fresh:
            print(f"\033[94mExpired Block was Modified: [{block.start}, {block.start + block_size}]\033[00m")
          
      # NACK
      elif len(response_fields) == 3:
        if DEBUG:
          _, _, error_message = response_fields
          print("Error in Read:", error_message)        
        
        satisfied_requests.insert_satisfied_read_request(selected_request.sequence, False, [])
        selected_request.block_application_semaphore.release()
        return
      
      # ACK
      elif len(response_fields) == 2:
        if DEBUG:
          print(f"\033[94mExpired Block was not Modified: [{block.start}, {block.start + block_size}]\033[00m")
        pass
      
      # Refresh Block Freshness
      block.t_fresh = time.time() + cache.fresh_t
        
      # Insert or Update Blocks
      selected_block = cache.find_block(file_id, block.start)
      if not selected_block: 
        # Append Block
        cache.insert_block(block)
      else:
        # Update Block
        selected_block.update_block(block.valid_block_size, block.t_fresh, block.t_modified, block.data)
    else:
      if DEBUG:
        print(f"\033[92mCache Hit: [{block.start}, {block.start + block_size}]\033[00m")
      
      
  satisfied_requests.insert_satisfied_read_request(selected_request.sequence, True, cached_blocks)
  selected_request.block_application_semaphore.release()


def handle_write(selected_request):
  request_type, file_id, reincarnation_number, block_size, fp_position, eof_offset, buffer_to_write, bytes_to_write = selected_request.fields
  
  if fp_position < 0 or eof_offset != None:
    write_data_request = Request(request_type, file_id, reincarnation_number, 'eof', eof_offset, bytes_to_write, buffer_to_write, block_size)
  else:
    write_data_request = Request(request_type, file_id, reincarnation_number, 'not_eof', fp_position, bytes_to_write, buffer_to_write, block_size)
  
  
  write_data_request.request_socket_fd.sendto(write_data_request.request, (SERVER_IP, SERVER_PORT))
  
  
  # When a Request for the EOF is sent we must first get the position of EOF to calculate the blocks needed
  if fp_position < 0 or eof_offset != None:
    response, _ = write_data_request.request_socket_fd.recvfrom(PACKET_LENGTH)
    response_fields = Request.parse_request(response)
    
    if len(response_fields) == 7:  
      response_type, status, t_modified, bytes_written, data, eof, current_offset = response_fields 
      
      # Set new Position since the EOF is not known
      fp_position = int(eof)
      
    cached_blocks = cache.get_blocks(file_id, fp_position, eof_offset + bytes_to_write)
    satisfied_blocks = 1
    
  else:
    cached_blocks = cache.get_blocks(file_id, fp_position, bytes_to_write)
    satisfied_blocks = 0
  
  for block in cached_blocks[satisfied_blocks:]:
    # Wait for the Respose
    response, _ = write_data_request.request_socket_fd.recvfrom(PACKET_LENGTH)
    response_fields = Request.parse_request(response)
    
    if len(response_fields) == 7:  
      response_type, status, t_modified, bytes_written, data, eof, current_offset = response_fields 
      
      block.valid_block_size = len(data)
      block.t_fresh = time.time() + cache.fresh_t
      block.t_modified = int(t_modified)
      block.data = data
      
      # Insert or Update Blocks
      selected_block = cache.find_block(file_id, block.start)
      if not selected_block: 
        # Append Block
        cache.insert_block(block)
      else:
        # Update Block
        selected_block.update_block(block.valid_block_size, block.t_fresh, block.t_modified, block.data)
    else:
      if DEBUG:
          _, _, error_message = response_fields
          print("Error in Write:", error_message)
      
      satisfied_requests.insert_satisfied_write_request(selected_request.sequence, False, -1, -1, -1)
      selected_request.block_application_semaphore.release()
      return
    
  satisfied_requests.insert_satisfied_write_request(selected_request.sequence, True, int(bytes_written.decode()), int(eof), int(current_offset))
  selected_request.block_application_semaphore.release()


def handle_truncate(selected_request):
  request_type, file_id, reincarnation_number, length = selected_request.fields
  print(request_type, file_id, reincarnation_number, length)
  
  truncate_request = Request(request_type, file_id, reincarnation_number, length)
  truncate_request.request_socket_fd.sendto(truncate_request.request, (SERVER_IP, SERVER_PORT))
  
  response, _ = truncate_request.request_socket_fd.recvfrom(PACKET_LENGTH)
  response_fields = Request.parse_request(response)
  
  print(response_fields)
  response_type, status, _ = response_fields
  if status != b'ACK':
    if DEBUG:
      print('Truncate Error:', response_fields[-1])
    
    satisfied_requests.insert_satisfied_truncate_request(selected_request.sequence, False)
    selected_request.block_application_semaphore.release()
    return
  
  
  t_modified = int(response_fields[-1])
  cache.truncate_reset_blocks(file_id, t_modified, time.time(), length)
  satisfied_requests.insert_satisfied_truncate_request(selected_request.sequence, True)
  selected_request.block_application_semaphore.release()
  
  
  
# Thread
def requests_handler():
  while True:
    requests_container.pending_requests_semaphore.acquire()
    requests_container.pending_requests_mutex.acquire()
    
    # Get Request
    selected_request = requests_container.pending_requests.pop(0)
    
    requests_container.pending_requests_mutex.release()

    request_type, *_ = selected_request.fields
    
    if request_type == 'LOOKUP_REQ':
      handle_lookup(selected_request=selected_request)
    elif request_type == 'READ_REQ':
      handle_read(selected_request=selected_request)
    elif request_type == 'WRITE_REQ':
      handle_write(selected_request=selected_request)
    elif request_type == 'TRUNCATE_REQ':
      handle_truncate(selected_request=selected_request)
    


def nfs_init(server_ip, server_port, cache_blocks, block_size, fresh_t):
  global SERVER_IP
  global SERVER_PORT
  global files_container
  global requests_container
  global cache
  global satisfied_requests
  
  SERVER_IP = server_ip
  SERVER_PORT = server_port
  requests_container = Requests()
  files_container = Files()
  cache = Cache(cache_blocks=cache_blocks, block_size=block_size, fresh_t=fresh_t)
  satisfied_requests = SatisfiedRequests()
  
  for _ in range(THREADS):
    request_handler_thread = threading.Thread(target=requests_handler)
    request_handler_thread.start()




def nfs_open(path, flags):
  request = Request('LOOKUP_REQ', path, flags)
  requests_container.insert_request(request)
  
  # Check Request Status
  satisfied_request = satisfied_requests.get_satisfied_lookup_request(request.sequence)
  if not satisfied_request:
    return -1
  elif not satisfied_request.status:
    return -1
  
  return files_container.get_fd_from_path(path)
  

def nfs_read(fd, length):
  selected_file = files_container.get_file_from_fd(fd)
  if not selected_file:
    return '', -1
  
  position, eof_offset = selected_file.get_position(fd)
  
  # Check Read Permission and Position in File
  if not selected_file.check_read_permission(fd) or position < 0 or eof_offset != None:
    return '', -1
  
  file_id = selected_file.file_id
  reincarnation_number = selected_file.get_reincarnation_number(fd)
  
  block_size = cache.block_size
  
  request = Request('READ_REQ', file_id, reincarnation_number, block_size, position, length)
  requests_container.insert_request(request)
  
  satisfied_request = satisfied_requests.get_satisfied_read_request(request.sequence)
  if not satisfied_request.status:
    return '', -1
  
  data, length = satisfied_request.get_data(position, length)
  
  # The FP MUST NOT Surpass the File Size
  files_container.update_position_by_fd(selected_file, fd, position, length)
  
  return data, length
  


def nfs_write(fd, buffer, length):
  selected_file = files_container.get_file_from_fd(fd)
  if not selected_file:
    return -1
  
  
  # Check Write Permission
  if not selected_file.check_write_permission(fd):
    return -1
  
  
  file_id = selected_file.file_id
  reincarnation_number = selected_file.get_reincarnation_number(fd)
  position, eof_offset = selected_file.get_position(fd)
  block_size = cache.block_size
  
  request = Request('WRITE_REQ', file_id, reincarnation_number, block_size, position, eof_offset, buffer, length)
  requests_container.insert_request(request)
  
  
  satisfied_request = satisfied_requests.get_satisfied_write_request(request.sequence)
  if not satisfied_request.status:
    return -1
  
  files_container.update_position_by_fd(selected_file, fd, 0, satisfied_request.current_offset)
  
  
  return satisfied_request.bytes_written

def nfs_seek(fd, offset, whence):
  selected_file = files_container.get_file_from_fd(fd)
  
  if not selected_file:
    return -1
  
  if whence == SEEK_SET:
    current_position = 0
  elif whence == SEEK_CUR:
    current_position, _ = selected_file.get_position(fd)
  elif whence == SEEK_END:
    current_position = EOF
  
  files_container.update_position_by_fd(selected_file, fd, current_position, offset)
  
  
def nfs_ftruncate(fd, length):
  selected_file = files_container.get_file_from_fd(fd)
  
  if not selected_file:
    return -1
  
  # Check Write Permission
  # if not selected_file.check_truncate_permission(fd):
  #   return -1

  file_id = selected_file.file_id
  reincarnation_number = selected_file.get_reincarnation_number(fd)
  
  request = Request('TRUNCATE_REQ', file_id, reincarnation_number, length)
  requests_container.insert_request(request)

  satisfied_request = satisfied_requests.get_satisfied_truncate_request(request.sequence)
  if not satisfied_request: 
    return -1
  if not satisfied_request.status:
    return -1
  
  return 0


def nfs_close(fd):
  selected_file = files_container.get_file_from_fd(fd)
  return selected_file.pop_fd(fd)
   
  