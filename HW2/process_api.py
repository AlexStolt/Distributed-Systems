import socket
import string
import struct
import threading
import time
import select
from ast import literal_eval as make_tuple
from dataclasses import dataclass
from tokenize import group

from attr import field



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
tcp_gi_fd = None      # Group Information
tcp_vfd_pi_fd = None  # Virtual File Descriptor and Processes Information
udp_fd = None         # UDP Multicast and Unicast


connected_processes = []

@dataclass(frozen=False, order=True)
class ServerInformation:
  # General Information
  virtual_file_descriptor: int
  group_name: string

  # Group Manager Related Information
  group_manager_tcp_address: tuple

  # Group Servers
  group_processes_information: list


################################################### HELPER FUNCTIONS ###################################################

# Initialize UDP (Multicast and Unicast) 
# and TCP (Member Addition Listener) Sockets
def api_init(TCP_UNICAST_HOST, TCP_UNICAST_PORT):
  global tcp_gi_fd
  global tcp_vfd_pi_fd
  global udp_fd
  
  # UDP Multicast Socket
  udp_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

  # Set the TTL for Messages to 1 so they stay in LAN
  ttl = struct.pack('b', 1)
  udp_fd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
  udp_fd.setblocking(False)

  # TCP Unicast Socket for Group Updates and Communication
  tcp_gi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_gi_fd.bind(('', 0))
  tcp_gi_fd.listen()

  # TCP Unicast Socket for Group Manager Virtual File Descriptor Packets
  tcp_vfd_pi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_vfd_pi_fd.bind(('', 0))
  tcp_vfd_pi_fd.listen()
  
  # !!!!!!!
  process_join_thread = threading.Thread(target=process_join_listener)
  process_join_thread.start()


# Send a "Reliable" UDP Multicast Request to Discover the
# Group Manager and Send Process Information
def multicast_reliable_communication(group_name, process_id):
  join_request = f'JOIN:{tcp_vfd_pi_fd.getsockname()}:{tcp_gi_fd.getsockname()}:{group_name}:{process_id}'
  
  i = 0
  while i < MULTICAST_TRIES:
    
    # Send to UDP Multicast
    start = time.time()
    udp_fd.sendto(join_request.encode(), (UDP_MULTICAST_GROUP, UDP_MULTICAST_PORT))

    while time.time() - start < MAXIMUM_MULTICAST_DELAY:
      readable, writable, errors = select.select([udp_fd], [], [], TIMEOUT)
      
      if udp_fd in readable:
        response, group_manager = udp_fd.recvfrom(PACKET_LENGTH)
        response = response.decode()
        if response != 'NACK':
          status, group_manager_tcp_address = response.split(":")
          return 0, group_manager_tcp_address
        
        return -2, None

    i = i + 1
  
  return -1, None



def process_join_listener():
  global tcp_gi_fd

  print('Hello From Thread')
  while True:
    connection_fd, address = tcp_gi_fd.accept()
    with connection_fd:
      data = connection_fd.recv(PACKET_LENGTH)
      data = data.decode()

      fields = data.split(':')
      if fields[0] != 'PIJR':
        continue

      group_name, process_id, process_udp_address = fields[1:]


      for process in connected_processes:
        if process.group_name != group_name:
          continue

        # Append Process Information to Group Related List
        process.group_processes_information.append({
          'process_id': process_id,
          'process_udp_address': process_udp_address
        })
      print("----------\n",connected_processes)




################################################### API FUNCTIONS ###################################################
def grp_join(group_name, process_id):
  global process_join_thread

  # Multicast Discovery (UDP)
  status, group_manager_tcp_address = multicast_reliable_communication(group_name, process_id)
  if status == -1:
    print("[ERROR]: Group Manager NOT Found")
    return -1
  elif status == -2:
    print("[ERROR]: Process Already in Group")
    return -1

  print("[SUCCESS]: Group Manager Found")


  # Unicast (TCP)
  while True:
    connection_fd, address = tcp_vfd_pi_fd.accept()
    with connection_fd:
      data = connection_fd.recv(PACKET_LENGTH)
      data = data.decode()
      
      # Decode Header
      fields = data.split(':')
      if fields[0] != 'VFD_PI':
        # Add Request Process Information
        continue
        
      virtual_file_descriptor = int (fields[1])

      connected_processes.append(ServerInformation(
        virtual_file_descriptor = virtual_file_descriptor,
        group_name = group_name,
        group_manager_tcp_address = group_manager_tcp_address,
        group_processes_information = []
      ))

      # Append Group Members
      for field in fields[2:]:
        group_member_process_id, group_member_udp_address = field.split('-')
        connected_processes[-1].group_processes_information.append({
          'process_id': group_member_process_id,
          'process_udp_address': make_tuple(group_member_udp_address)
        })
      
      # Insert Self on the Begining of the List
      connected_processes[-1].group_processes_information.insert(0, {
        'process_id': process_id,
        'process_udp_address': udp_fd.getsockname()
      })
      
      break
  
  return virtual_file_descriptor






