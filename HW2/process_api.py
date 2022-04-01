import random
import socket
import string
import struct
import threading
import time
import select
from ast import literal_eval as make_tuple
from dataclasses import dataclass

IP = None
NETWORK_LATENCY = 2
NETWORK_RELIABILITY =  100

PACKET_LENGTH = 1024
TRIES = 4
RTT = 4
TIMEOUT = 1

UDP_MULTICAST_GROUP = '224.1.1.1'
UDP_MULTICAST_PORT = 8000

# Sockets
tcp_gi_fd = None      # Group Information
tcp_vfd_pi_fd = None  # Virtual File Descriptor and Processes Information
udp_unicast_receiver_fd = None 
udp_unicast_sender_fd = None
tcp_pi_fd = None

connected_processes = []

@dataclass(frozen=False, order=True)
class ServerInformation:
  # General Information
  virtual_file_descriptor: int
  group_name: string
  process_id: string
  
  # Locks and Semaphores
  group_processes_information_list_mutex: any
  receive_block_semaphore: any
  
  # Group Manager Related Information
  group_manager_tcp_address: tuple

  # Group Servers
  group_processes_information: list


################################################### HELPER FUNCTIONS ###################################################

# Initialize UDP (Multicast and Unicast) 
# and TCP (Member Addition Listener) Sockets
def api_init(HOST_IP, TCP_UNICAST_PORT):
  global IP
  global tcp_gi_fd
  global udp_unicast_receiver_fd
  global udp_unicast_sender_fd
  global tcp_pi_fd
  
  IP = HOST_IP
  
  # UDP Unicast Socket (Listener)
  udp_unicast_receiver_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_unicast_receiver_fd.bind((IP, 0))
  
  # UDP Unicast Socket (Sender)
  udp_unicast_sender_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_unicast_sender_fd.bind((IP, 0))
  udp_unicast_sender_fd.setblocking(False)
  
  # TCP Socket (Listener)
  tcp_pi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_pi_fd.bind((IP, 0))
  tcp_pi_fd.listen()
  
  # udp_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  # udp_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

  # # Set the TTL for Messages to 1 so they stay in LAN
  # ttl = struct.pack('b', 1)
  # udp_fd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
  # # udp_fd.setblocking(False)

  # TCP Unicast Socket for Group Updates and Communication
  # tcp_gi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  # tcp_gi_fd.bind(('127.0.0.1', 0))
  # tcp_gi_fd.listen()

  # TCP Unicast Socket for Group Manager Virtual File Descriptor Packets
  # tcp_vfd_pi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  # tcp_vfd_pi_fd.bind(('127.0.0.1', 0))
  # tcp_vfd_pi_fd.listen()
  
  # Start Listeners for TCP and UDP
  tcp_process_join_thread = threading.Thread(target=tcp_listener)
  tcp_process_join_thread.start()
    
  udp_unicast_thread = threading.Thread(target=udp_listener)
  udp_unicast_thread.start()
  
  


# Send a "Reliable" UDP Multicast Request to Discover the
# Group Manager and Send Process Information
def multicast_reliable_communication(group_name, process_id, tcp_vfd_pi_address, tcp_pi_address, udp_unicast_address):
  join_request = f'{tcp_vfd_pi_address}:{tcp_pi_address}:{udp_unicast_address}:{group_name}:{process_id}'
  
  # Create a Multicast UDP Socket
  udp_multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  ttl = struct.pack('b', 1)
  udp_multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
  udp_multicast_fd.setblocking(False)
  
  
  i = 0
  while i < TRIES:
    # Send to UDP Multicast
    start = time.time()
    udp_multicast_fd.sendto(join_request.encode(), (UDP_MULTICAST_GROUP, UDP_MULTICAST_PORT))

    while time.time() - start < RTT:
      readable, writable, errors = select.select([udp_multicast_fd], [], [], TIMEOUT)
      
      if udp_multicast_fd in readable:
        response, group_manager = udp_multicast_fd.recvfrom(PACKET_LENGTH)
        response = response.decode()
        if response != 'NACK':
          status, group_manager_tcp_address = response.split(":")
          udp_multicast_fd.close()
          
          return 0, group_manager_tcp_address
        
        udp_multicast_fd.close()
        return -2, None

    i = i + 1
  
  udp_multicast_fd.close()
  return -1, None


def unicast_reliable_communication(udp_unicast_destination_address, payload):
  
  while True:
    # Send to UDP Unicast
    udp_unicast_sender_fd.sendto(payload.encode(), udp_unicast_destination_address)
    print('Loop')
    readable, _, _ = select.select([udp_unicast_sender_fd], [], [], None)
    
    if len(readable) > 0:
      print(len(readable))
      try:
        response, group_manager = udp_unicast_sender_fd.recvfrom(PACKET_LENGTH)
        response = response.decode()
        print(response)
        return
      except:
        break

def tcp_listener():
  
  while True:
    group_manager_fd, group_manager_address = tcp_pi_fd.accept()
    with group_manager_fd:
      data = group_manager_fd.recv(PACKET_LENGTH)
      data = data.decode()
      fields = data.split(':')
    
      group_name, process_id, process_udp_unicast_address = fields

      
      for process in connected_processes:
        if process.group_name != group_name:
          continue

        process.group_processes_information_list_mutex.acquire()

        # Append Process Information to Group Related List
        process.group_processes_information.append({
          'process_id': process_id,
          'process_udp_address': make_tuple(process_udp_unicast_address),
          'send_sequence': 0, 
          'receive_sequence': 0,
          'pending_message_buffer': []
        })
        #print(len(process.group_processes_information))
        group_manager_fd.sendall("ACK".encode())
        process.group_processes_information_list_mutex.release()
        
        
        
        
def udp_listener():
  while True:
    
    message, source_process_address = udp_unicast_receiver_fd.recvfrom(PACKET_LENGTH)
    message = message.decode()
    
    process_id, group_name, payload, receive_sequence = message.split(':')
    
    # Simulating Packet Losses
    if random.randint(1, 100) > NETWORK_RELIABILITY:
      #print('Packet was Lost')
      print(source_process_address, udp_unicast_sender_fd.getsockname())
      continue
    
    # Notify Sender that Data was Received
    udp_unicast_receiver_fd.sendto('ACK'.encode(), source_process_address)
    #print('ACK was send')
    for process in connected_processes:
      if process.group_name != group_name:
        continue
      # print('**',payload)
      process.group_processes_information_list_mutex.acquire()
      
      for group_process in process.group_processes_information:
        if group_process['process_id'] != process_id:
          #print('---', group_process['process_id'], process_id)
          continue
        
        # print('***',payload)
        group_process['pending_message_buffer'].append({
          'sequence': receive_sequence,
          'payload': payload
        })
        # print(group_process['pending_message_buffer'])
      
      
      process.group_processes_information_list_mutex.release()
      process.receive_block_semaphore.release()
    # print(message)
    # print(connected_processes)




################################################### API FUNCTIONS ###################################################
def grp_join(group_name, process_id):
  # Socket to Receive Virtual File Descriptor and Process Inforation
  tcp_vfd_pi_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  tcp_vfd_pi_fd.bind((IP, 0))
  tcp_vfd_pi_fd.listen()
  
  
  # Multicast Discovery (UDP)
  status, group_manager_tcp_address = multicast_reliable_communication(
    group_name, 
    process_id, 
    tcp_vfd_pi_fd.getsockname(),
    tcp_pi_fd.getsockname(),
    udp_unicast_receiver_fd.getsockname()
  )
  
  if status == -1:
    print("[ERROR]: Group Manager NOT Found")
    return -1
  elif status == -2:
    print("[ERROR]: Process Already in Group")
    return -1

  print(f"[SUCCESS]: Group Manager Found at {group_manager_tcp_address}")


  # Unicast (TCP)
  while True:
    connection_fd, address = tcp_vfd_pi_fd.accept()
    with connection_fd:
      data = connection_fd.recv(PACKET_LENGTH)
      data = data.decode()
      
    
      # Decode Header
      fields = data.split(':')
      virtual_file_descriptor = int (fields[0])
      
      connected_processes.append(ServerInformation(
        virtual_file_descriptor = virtual_file_descriptor,
        group_name = group_name,
        process_id = process_id,
        group_processes_information_list_mutex = threading.Lock(),
        receive_block_semaphore = threading.Semaphore(0),
        group_manager_tcp_address = group_manager_tcp_address,
        group_processes_information = []
      ))

      connected_processes[-1].group_processes_information_list_mutex.acquire()

      # Append Group Members   
      for field in fields[1:]:
        group_member_process_id, group_member_udp_address = field.split('-')
        
        connected_processes[-1].group_processes_information.append({
          'process_id': group_member_process_id,
          'process_udp_address': make_tuple(group_member_udp_address),
          'send_sequence': 0, 
          'receive_sequence': 0,
          'pending_message_buffer': []
        })
        
        
      # Insert Self on the Begining of the List
      connected_processes[-1].group_processes_information.insert(0, {
        'process_id': process_id,
        'process_udp_address': udp_unicast_receiver_fd.getsockname(),
        'send_sequence': 0,
        'receive_sequence': 0,
        'pending_message_buffer': []
      })
      
      connected_processes[-1].group_processes_information_list_mutex.release()
    
      
      break
    
  
  return virtual_file_descriptor




def grp_send(file_descriptor, payload, payload_length, causal_total):
  # FIFO
  if not causal_total:
    for process in connected_processes:
      if process.virtual_file_descriptor != file_descriptor:
        continue
      
      message = f'{process.process_id}:{process.group_name}:{payload}'
      
      process.group_processes_information_list_mutex.acquire()
      
      for group_process in process.group_processes_information:
        # SLEEP
        
        # if random.randint(0, 100) < NETWORK_RELIABILITY:
          
        
        # Reliably Send Data to Processes
        unicast_reliable_communication(group_process['process_udp_address'], f"{message}:{group_process['send_sequence']}")
        
        # WAIT FOR ACK
        
        # ACK WAS RECEIVED
        group_process['send_sequence'] = group_process['send_sequence'] + 1
      
      process.group_processes_information_list_mutex.release() 
  
 
        
        
def grp_recv(file_descriptor, blocking):
  while True:
    for process in connected_processes:
      if process.virtual_file_descriptor != file_descriptor:
        continue
      
      process.group_processes_information_list_mutex.acquire()
      
      for group_process in process.group_processes_information:
        for message in group_process['pending_message_buffer'][:]:
          
          if int (message['sequence']) != int (group_process['receive_sequence']):
            continue
          
          group_process['pending_message_buffer'].remove(message)
          group_process['receive_sequence'] = group_process['receive_sequence'] + 1
          
         
          process.group_processes_information_list_mutex.release()
         
          return message['payload'], len(message['payload'])

      process.group_processes_information_list_mutex.release()
    
    #time.sleep(10)
    #print(connected_processes)
    if not blocking:
      break
    
    # Bloc Execution
    for process in connected_processes:
      if process.virtual_file_descriptor != file_descriptor:
        continue
      
      for _ in range(process.receive_block_semaphore._value):
        process.receive_block_semaphore.acquire()
      break
      
  return None, -1
    
    
    