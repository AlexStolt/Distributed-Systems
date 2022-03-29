from concurrent.futures import process
import socket
import string
import struct
from dataclasses import dataclass
from ast import literal_eval as make_tuple
from tokenize import group

from attr import field

PACKET_LENGTH = 1024
VIRTUAL_FILE_DESCRIPTOR = 0

UDP_MULTICAST_GROUP = '224.1.1.1'
UDP_MULTICAST_PORT = 8000


TCP_UNICAST_HOST = "127.0.0.1"
TCP_UNICAST_PORT = 8080


connected_processes = []

@dataclass(frozen=True, order=True)
class ProcessInformation:
  # General Information
  group_name: string
  process_id: string
  virtual_file_descriptor: int

  # TCP Information
  tcp_group_socket_address: tuple

  # UDP Information
  udp_address: tuple


def multicast_socket_init():
  # UDP Multicast Socket
  udp_multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  udp_multicast_fd.bind((UDP_MULTICAST_GROUP, UDP_MULTICAST_PORT))

  memory_request = struct.pack("4sl", socket.inet_aton(UDP_MULTICAST_GROUP), socket.INADDR_ANY)
  udp_multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, memory_request)
  # udp_multicast_fd.setblocking(False)

  # Unicast Socket for Process Group Leave
  tcp_leave_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_leave_fd.bind((TCP_UNICAST_HOST, TCP_UNICAST_PORT))
  # tcp_unicast_fd.bind(('', 0))
  # listen 
  # accept



  return tcp_leave_fd, udp_multicast_fd


if __name__ == "__main__":
  tcp_leave_fd, udp_multicast_fd = multicast_socket_init()

  while True:
    request, udp_process_address = udp_multicast_fd.recvfrom(PACKET_LENGTH)
    request = request.decode()
    
    fields = request.split(':')

    # Process Leaves Group
    if fields[0] != 'JOIN':
      # Process Might Want to Leave
      #
      #
      continue

    # TCP Related Information
    tcp_vfd_pi_socket_address = make_tuple(fields[1])
    tcp_group_socket_address = make_tuple(fields[2])
    

    # General Information
    group_name = fields[3]
    process_id = fields[4]

    # Check for Duplicate Pair of Group Name and Process ID
    process_exists = False
    for process in connected_processes:
      if process.group_name != group_name or process.process_id != process_id:
        continue
      process_exists = True
      

    if process_exists:
      udp_multicast_fd.sendto("NACK".encode(), udp_process_address)
      continue
    

    # Process is Connected to Group Manager
    connected_processes.append(ProcessInformation(
      group_name = group_name,
      process_id = process_id,
      virtual_file_descriptor = VIRTUAL_FILE_DESCRIPTOR,
      tcp_group_socket_address = tcp_group_socket_address,
      udp_address = udp_process_address,
    ))

    udp_multicast_fd.sendto(f"ACK:{tcp_leave_fd.getsockname()}".encode(), udp_process_address)
    

    # Virtual File Descriptor and Processes Information
    processes_information_response = f"VFD_PI:{connected_processes[-1].virtual_file_descriptor}" 
   
    # Notify and Update Processes about the Member that Joined
    for process in connected_processes[:-1]:
      if process.group_name != connected_processes[-1].group_name:
        continue
      
      # TCP Unicast Socket for Each Server EXCEPT the Currently Joined Member
      tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      tcp_communication_fd.connect(process.tcp_group_socket_address)
      
      # Process Information Join Request
      tcp_communication_fd.sendall(f"PIJR:{connected_processes[-1].group_name}:{connected_processes[-1].process_id}:{udp_process_address}".encode()) 
      tcp_communication_fd.close()
      
      
      # Processes Accumulated Information String
      processes_information_response = processes_information_response + ":" + f"{process.process_id}-{process.udp_address}"
    

    # Send Servers Information to Currently Subscribed Member
    tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_communication_fd.connect(tcp_vfd_pi_socket_address)
    tcp_communication_fd.sendall(processes_information_response.encode())
    tcp_communication_fd.close()
    