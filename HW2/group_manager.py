import socket
import string
import struct
import threading
from dataclasses import dataclass
from ast import literal_eval as make_tuple
import sys
from process_api import tcp_listener



PACKET_LENGTH = 1024
VIRTUAL_FILE_DESCRIPTOR = 0

UDP_MULTICAST_GROUP = '224.1.1.1'
UDP_MULTICAST_PORT = 8000


TCP_UNICAST_HOST = None

connected_processes = []

@dataclass(frozen=True, order=True)
class ProcessInformation:
  # General Information
  group_name: string
  process_id: string
  virtual_file_descriptor: int

  # TCP Information
  tcp_pi_address: tuple
   
      

  # UDP Information
  udp_unicast_address: tuple


def multicast_socket_init():
  # UDP Multicast Socket
  udp_multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_multicast_fd.bind((UDP_MULTICAST_GROUP, UDP_MULTICAST_PORT))
  memory_request = struct.pack("4sl", socket.inet_aton(UDP_MULTICAST_GROUP), socket.INADDR_ANY)
  udp_multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, memory_request)
  # udp_multicast_fd.setblocking(False)

  # Unicast Socket for Process Group Leave
  tcp_leave_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_leave_fd.bind((TCP_UNICAST_HOST, 0))
  # tcp_unicast_fd.bind(('', 0))
  tcp_leave_fd.listen() 
  # accept

  tcp_listener_thread = threading.Thread(target=tcp_listener, args=(tcp_leave_fd, ))
  tcp_listener_thread.start()
    

  return tcp_leave_fd, udp_multicast_fd, tcp_listener_thread

def tcp_listener(tcp_leave_fd):
  while True:
    process_fd, process_address = tcp_leave_fd.accept()
    with process_fd:
      data = process_fd.recv(PACKET_LENGTH)
      data = data.decode()
      fields = data.split(':')
      virtual_file_descriptor, group_name, process_id = fields
      
      #Send to the others of the group message that someone is leaving to update their lists
      for process in connected_processes:
        if process.group_name == group_name and process.virtual_file_descriptor != int (virtual_file_descriptor):
          tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          tcp_communication_fd.connect(process.tcp_pi_address)
          tcp_communication_fd.sendall(f"LEAVE:{group_name}:{process_id}".encode()) 
          data = tcp_communication_fd.recv(PACKET_LENGTH)
          tcp_communication_fd.close()
        
      ###Send ack
      process_fd.sendall("LEAVE".encode())
      
      #Remove process
      for process in connected_processes[:]:
        if process.virtual_file_descriptor == virtual_file_descriptor:
          connected_processes.remove(process)
          break

      print(f'<Success> Remove from group {group_name} the {process_id}')

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("python3 <EXECUTABLE> <IP>")
    exit(-1)

  TCP_UNICAST_HOST = sys.argv[1]



  tcp_leave_fd, udp_multicast_fd, tcp_listener_thread = multicast_socket_init()
  
  
  
  while True:
    request, udp_process_address = udp_multicast_fd.recvfrom(PACKET_LENGTH)
    request = request.decode()
    fields = request.split(':')

    # Socket Related Information
    tcp_vfd_pi_address = make_tuple(fields[0])
    tcp_pi_address = make_tuple(fields[1])
    udp_unicast_address = make_tuple(fields[2])
    
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
      tcp_pi_address = tcp_pi_address,
      udp_unicast_address = udp_unicast_address,
    ))
    
    print(f'<Success> Join in group {group_name} the {process_id}')

    udp_multicast_fd.sendto(f'ACK:{tcp_leave_fd.getsockname()}'.encode(), udp_process_address)
    

    # Virtual File Descriptor and Processes Information
    processes_information_response = f'{connected_processes[-1].virtual_file_descriptor}' 
   
    # Notify and Update Processes about the Member that Joined
    for process in connected_processes[:-1]:
      if process.group_name != connected_processes[-1].group_name:
        continue
      
      # TCP Unicast Socket for Each Server EXCEPT the Currently Joined Member
      tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      tcp_communication_fd.connect(process.tcp_pi_address)
      tcp_communication_fd.sendall(f"JOIN:{connected_processes[-1].group_name}:{connected_processes[-1].process_id}:{udp_unicast_address}".encode()) 
      data = tcp_communication_fd.recv(PACKET_LENGTH)
      tcp_communication_fd.close()
      
      
      # Processes Accumulated Information String
      processes_information_response = processes_information_response + ":" + f"{process.process_id}-{process.udp_unicast_address}"
    

    # Send Servers Information to Currently Subscribed Member
    tcp_communication_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_communication_fd.connect(tcp_vfd_pi_address)
    tcp_communication_fd.sendall(processes_information_response.encode())
    tcp_communication_fd.close()
    
    VIRTUAL_FILE_DESCRIPTOR = VIRTUAL_FILE_DESCRIPTOR + 1
    
    
  