import socket
import string
import struct
import threading
import time
import select
from ast import literal_eval as make_tuple
from dataclasses import dataclass



process_join_thread = None

NETWORK_LATENCY = 2
NETWORK_STABILITY = 50

PACKET_LENGTH = 1024
MULTICAST_TRIES = 4
MAXIMUM_MULTICAST_DELAY = 4
TIMEOUT = 1

UDP_MULTICAST_GROUP = '224.1.1.1'
UDP_MULTICAST_PORT = 8000

# Sockets
udp_multicast_fd = None
tcp_unicast_fd = None

connected_processes = []

@dataclass(frozen=False, order=True)
class ServerInformation:
  # General Information
  virtual_file_descriptor: int
  group_name: string

  # Group Manager Related Information
  group_manager_tcp_address: tuple

  # Group Servers
  group_processes: list


def api_init(TCP_UNICAST_HOST, TCP_UNICAST_PORT):
  global udp_multicast_fd
  global tcp_unicast_fd


  # UDP Multicast Socket
  udp_multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

  # Set the time-to-live for messages to 1 so they stay in LAN
  ttl = struct.pack('b', 1)
  udp_multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
  udp_multicast_fd.setblocking(False)

  # TCP Unicast Socket for Virtual File Descriptor
  tcp_unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_unicast_fd.bind(('', 0))
  tcp_unicast_fd.listen()


################################################### HELPER FUNCTIONS ###################################################
def multicast_reliable_communication(group_name, process_id):
  join_request = f'JOIN:{tcp_unicast_fd.getsockname()}:{group_name}:{process_id}'
  
  i = 0
  while i < MULTICAST_TRIES:
    
    # Send to UDP Multicast
    start = time.time()
    udp_multicast_fd.sendto(join_request.encode(), (UDP_MULTICAST_GROUP, UDP_MULTICAST_PORT))

    while time.time() - start < MAXIMUM_MULTICAST_DELAY:
      readable, writable, errors = select.select([udp_multicast_fd], [], [], TIMEOUT)
      
      if udp_multicast_fd in readable:
        response, group_manager = udp_multicast_fd.recvfrom(PACKET_LENGTH)
        response = response.decode()
        if response != 'NACK':
          status, tcp_address = response.split(":")
          return 0, tcp_address
        
        return -2, None

    i = i + 1
  
  return -1, None



def process_join_listener():
  global tcp_unicast_fd

  print('Hello From Thread')
  while True:
    connection_fd, address = tcp_unicast_fd.accept()
    with connection_fd:
      data = connection_fd.recv(PACKET_LENGTH)
      
      print("Hello",data)




################################################### API FUNCTIONS ###################################################
def grp_join(group_name, process_id):
  global process_join_thread
  global tcp_unicast_fd

  # Multicast (UDP)
  status, tcp_address = multicast_reliable_communication(group_name, process_id)
  if status == -1:
    print("[ERROR]: Group Manager NOT Found")
    return -1
  elif status == -2:
    print("[ERROR]: Process Already in Group")
    return -1

  print("[SUCCESS]: Group Manager Found")


  # Unicast (TCP)
  while True:
    connection_fd, address = tcp_unicast_fd.accept()
    with connection_fd:
      data = connection_fd.recv(PACKET_LENGTH)
      data = data.decode()
      
      # Decode Header
      fields = data.split(':')
      if fields[0] != 'VFD_PI':
        # Add Request Process Information
        print("HITTTTTTTTTTTTTTTTTTTTTTTTTT")
        continue
        
      virtual_file_descriptor = int (fields[1])


      connected_processes.append(ServerInformation(
        virtual_file_descriptor = virtual_file_descriptor,
        group_name = group_name,
        group_manager_tcp_address = tcp_address,
        group_processes = []
      ))

      # Append Group Members
      for field in fields[2:]:
        connected_processes[-1].group_processes.append(make_tuple(field))
        
      process_join_thread = threading.Thread(target=process_join_listener)
      process_join_thread.start()
      
      break
  
  return virtual_file_descriptor






