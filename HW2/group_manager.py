from concurrent.futures import process
import socket
import string
import struct
from dataclasses import dataclass
from ast import literal_eval as make_tuple
from tokenize import group

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
  tcp_address: tuple

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
  tcp_unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_unicast_fd.bind((TCP_UNICAST_HOST, TCP_UNICAST_PORT))
  # tcp_unicast_fd.bind(('', 0))
  # listen 
  # accept



  return tcp_unicast_fd, udp_multicast_fd


if __name__ == "__main__":
  tcp_unicast_fd, udp_multicast_fd = multicast_socket_init()

  while True:
    request, process_address = udp_multicast_fd.recvfrom(PACKET_LENGTH)
    request = request.decode()
    
    fields = request.split(':')
    
    # Process Leaves Group
    if fields[0] != 'JOIN':
      pass
    

    # Process Joins Group

    # TCP Related Information
    tcp_information = make_tuple(fields[1])
    

    # General Information
    group_name = fields[2]
    process_id = fields[3]

    

    process_information = ProcessInformation(
      group_name = group_name,
      process_id = process_id,
      virtual_file_descriptor = VIRTUAL_FILE_DESCRIPTOR,
      tcp_address = tcp_information,
      udp_address = process_address,
    )
    
    # Check for Duplicate Pair of Group Name and Process ID
    process_exists = False
    for process in connected_processes:
      if process.group_name != process_information.group_name:
        continue
      if process.process_id != process_information.process_id:
        continue
      process_exists = True
      

    if process_exists:
      udp_multicast_fd.sendto("NACK".encode(), process_address)
      continue

    connected_processes.append(process_information)
    udp_multicast_fd.sendto(f"ACK:{tcp_unicast_fd.getsockname()}".encode(), process_address)
    

    #Sent to other information for the new
    processes_information_response = f"VFD_PI:{process_information.virtual_file_descriptor}" # Virtual File Descriptor and Processes Information
   
    # Notify Servers About the Member that wants to Join
    for process in connected_processes:
      if process.group_name != process_information.group_name:
        continue
      if process.process_id != process_information.process_id:
        # TCP Unicast Socket for Each Server EXCEPT the New Member
        tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_communication_fd.connect(process.tcp_address)
        tcp_communication_fd.sendall(f"PIJR:{process_information.group_name}:{process_information.process_id}:{process_address}".encode()) # Process Information Join Request
        tcp_communication_fd.close()
      
      # Processes Accumulated Information String
      processes_information_response = processes_information_response + ":" + f"{process.udp_address}"
    

    # Send Servers Information to Currently Subscribed Member
    tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_communication_fd.connect(process_information.tcp_address)
    tcp_communication_fd.sendall(processes_information_response.encode())
    tcp_communication_fd.close()
    