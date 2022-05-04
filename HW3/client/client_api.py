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
  request_type, file_id, block_size, position, length = selected_request.fields
  
  cached_blocks = cache.get_blocks(file_id, position, length)
  # Reconstruct Response Buffered from the Valid Cache Blocks
  
  # Request Missing Blocks or Blocks that have Expired
  for block in cached_blocks:
    # Check if Block is Valid (If Block is Valid the Block is in Cache)
    if not block.is_valid:
      missing_blocks_request = Request(request_type, file_id, block.start, block_size)
      missing_blocks_request.request_socket_fd.sendto(missing_blocks_request.request, (SERVER_IP, SERVER_PORT))
    
      # Wait for the Respose
      response, _ = missing_blocks_request.request_socket_fd.recvfrom(PACKET_LENGTH)
      response_fields = Request.parse_request(response)
      response_type, t_modified, data = response_fields 
      
      # Modified Block
      block.valid_block_size = len(data)
      block.t_fresh = time.time() + cache.fresh_t
      block.t_modified = int(t_modified)
      block.data = data
      
      selected_block = cache.find_block(file_id, block.start)
      if not selected_block: 
        # Append Block
        cache.insert_block(block)
      else:
        # Update Block
        selected_block.update_block(block.valid_block_size, block.t_fresh, block.t_modified, block.data)
    
    elif block.is_valid and not block.is_fresh:
      # Check NFS Freshness Parameters
      print("Expired Block")
      pass
      
  satisfied_requests.insert_satisfied_request(selected_request.sequence, cached_blocks)
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
  pass

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