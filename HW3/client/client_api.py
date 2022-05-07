from turtle import position
from classes import *

# File Operations
O_RDONLY  =   0
O_WRONLY  =   1
O_RDWR    =   2
O_CREAT   =   100
O_EXCL    =   200
O_TRUNC   =   1000


# Whence Identifiers
SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

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
  
  
  # Check Locally if File Already Exists
  selected_file = files_container.get_file_by_path(file_path)
  if not selected_file:
    return False
  
  # Append FD
  files_container.append_file(selected_file.file_path, selected_file.file_path)
  return True

def handle_lookup(selected_request):
  # Try to Satisfy Request without Contacting the Server
  if handle_lookup_locally(selected_request):
    # Unblock Application
    selected_request.block_application_semaphore.release()
    return
  
  # Send Request to Server
  selected_request.request_socket_fd.sendto(selected_request.request, (SERVER_IP, SERVER_PORT))
  
  
  # Wait for the Respose
  response, _ = selected_request.request_socket_fd.recvfrom(PACKET_LENGTH)
  response_fields = Request.parse_request(response)
  print(response)
  # Handle Lookup Requests
  try:
    response_type, status, file_path, file_id = response_fields 
  except:
    response_type, status = response_fields
  
  if status != b'ACK':
    # Unblock Application
    selected_request.block_application_semaphore.release()
    return
  
  
  files_container.append_file(file_path.decode(), int(file_id.decode()))
  selected_request.block_application_semaphore.release()


def handle_read(selected_request):
  request_type, file_id, block_size, fp_position, length = selected_request.fields
  
  # Get Blocks from Cache
  cached_blocks = cache.get_blocks(file_id, fp_position, length)
  
  # Request Missing Blocks or Blocks that have Expired
  for block in cached_blocks:
    # Check if Block is Valid (If Block is Valid the Block is in Cache) and if Block is Fresh 
    if (not block.is_valid) or (block.is_valid and not block.is_fresh):
      
      # Cache Miss
      if not block.is_valid:
        if DEBUG:
          print(f"\033[91mCache Miss: [Start: {block.start}, Size: {block.valid_block_size}]\033[00m")
      
      # Cache Block Expiration
      elif block.is_valid and not block.is_fresh:
        if DEBUG:
          print(f"\033[93mExpired Block: [Start: {block.start}, Size: {block.valid_block_size}]\033[00m")
      
      
      # Create the Request
      request = Request(request_type, file_id, block.start, block_size, block.t_modified)
      print(request_type, file_id, block.start, block_size, block.t_modified)
      # Send Request to Server
      request.request_socket_fd.sendto(request.request, (SERVER_IP, SERVER_PORT))
    
      # Wait for the Respose
      response, _ = request.request_socket_fd.recvfrom(PACKET_LENGTH)
      response_fields = Request.parse_request(response)
      
      if len(response_fields) > 2:
        # Block was Refreshed
        response_type, status, t_modified, data = response_fields 
        
        # Modified Block
        block.valid_block_size = len(data)
        block.t_modified = int(t_modified)
        block.data = data
      else:
        if DEBUG:
          print(f"\033[93mExpired Block: [Start: {block.start}] is Fresh\033[00m")
      
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
        print(f"\033[92mCache Hit: [Start: {block.start}, Size: {block.valid_block_size}]\033[00m")
      
      
  satisfied_requests.insert_satisfied_request(selected_request.sequence, cached_blocks)
  selected_request.block_application_semaphore.release()




def handle_write(selected_request):
  request_type, file_id, block_size, fp_position, buffer_to_write, bytes_to_write = selected_request.fields
  print(request_type, file_id, fp_position, buffer_to_write, bytes_to_write)
  
  
  write_data_request = Request(request_type, file_id, fp_position, bytes_to_write, buffer_to_write, block_size)
  write_data_request.request_socket_fd.sendto(write_data_request.request, (SERVER_IP, SERVER_PORT))
  
  cached_blocks = cache.get_blocks(file_id, fp_position, bytes_to_write)
  for block in cached_blocks:    
    # Wait for the Respose
    response, _ = write_data_request.request_socket_fd.recvfrom(PACKET_LENGTH)
    response_fields = Request.parse_request(response)
    if len(response_fields) > 2:  
      print(response_fields)
      response_type, status, t_modified, data = response_fields 
      
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
  
  
  selected_request.block_application_semaphore.release()
  
  for block in cache.blocks:
    print(block)
  
  
  
# Thread
def requests_handler():
  while True:
    requests_container.pending_requests_semaphore.acquire()
    requests_container.pending_requests_mutex.acquire()
    
    # Get Request
    selected_request = requests_container.pending_requests.pop(0)
    
    requests_container.pending_requests_mutex.release()

    request_type, *_ = selected_request.fields
    print(request_type)
    if request_type == 'LOOKUP_REQ':
      handle_lookup(selected_request=selected_request)
    elif request_type == 'READ_REQ':
      handle_read(selected_request=selected_request)
    elif request_type == 'WRITE_REQ':
      handle_write(selected_request=selected_request)

    
    







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
  requests_container.insert_request(Request('LOOKUP_REQ', path, flags))
  return files_container.get_fd_from_path(path)
  




def nfs_read(fd, length):
  selected_file = files_container.get_file_from_fd(fd)
  file_id = selected_file.file_id
  position = selected_file.get_position(fd)
  block_size = cache.block_size
  
  request = Request('READ_REQ', file_id, block_size, position, length)
  requests_container.insert_request(request)
  
  satisfied_request = satisfied_requests.get_satisfied_request(request.sequence)
  data, length = satisfied_request.get_data(position, length)
  
  # The FP MUST NOT Surpass the File Size
  files_container.update_position_by_file(selected_file, fd, position + length)
  # print(selected_file.get_position(fd))
  
  return data, length
  


def nfs_write(fd, buffer, length):
  selected_file = files_container.get_file_from_fd(fd)
  file_id = selected_file.file_id
  position = selected_file.get_position(fd)
  block_size = cache.block_size
  
  request = Request('WRITE_REQ', file_id, block_size, position, buffer, length)
  requests_container.insert_request(request)
  print("Write Complete")
  

def nfs_seek(fd, offset, whence):
  selected_file = files_container.get_file_from_fd(fd)
  
  
  if whence == SEEK_SET:
    position = offset
  elif whence == SEEK_CUR:
    position = selected_file.get_position(fd) + offset
  elif whence == SEEK_END: # MUST BE CHANGED ERROR
    position = -1
  
  print(position)
  files_container.update_position_by_file(selected_file, fd, position)
  
  
def nfs_ftruncate(fd, length):
  pass


def nfs_close(fd):
  pass 