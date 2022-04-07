import random
import socket
import string
import struct
import threading
import time
import select
from ast import literal_eval as make_tuple
from dataclasses import dataclass
from queue import Queue
import sys


process_priority = random.randint(0,100) # !!! THIS MUST CHANGE

IP = None
NETWORK_LATENCY = 1
NETWORK_RELIABILITY =  100
DISPLAY_HISTORY = False

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
tcp_pi_fd = None

#Buffers
PENDING_INSERTS = []
PENDING_PROPOSALS = Queue()
PENDING_UPDATES = Queue()



UNSTABLE_SEQUENCE = 0 

unicast_reliable_communication_mutex = threading.Lock()
join_group_mutex = threading.Lock()



group_information = []

@dataclass(frozen=False, order=True)
class ServerInformation:
  # General Information
  virtual_file_descriptor: int
  group_name: string
  process_id: string
  
  # Socket File Descriptors
  udp_unicast_sender_fd: int
  
  # Total Causal Related Information
  process_priority: int
  process_sequence: int
  delivered_messages: list
  
  # Locks and Semaphores
  connected_processes_mutex: any
  receive_block_semaphore: any
  
  # Group Manager Related Information
  group_manager_tcp_address: tuple

  # Group Servers
  connected_processes: list
  
  # List of Messages Waiting Proposals
  unstable_message_buffer: list


################################################### HELPER FUNCTIONS ###################################################

# Initialize UDP (Multicast and Unicast) 
# and TCP (Member Addition Listener) Sockets
def api_init(HOST_IP):
  global IP
  global tcp_gi_fd
  global udp_unicast_receiver_fd
  global tcp_pi_fd
  
  IP = HOST_IP
  
  # UDP Unicast Socket (Listener)
  udp_unicast_receiver_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  udp_unicast_receiver_fd.bind((IP, 0))
  
  # UDP Unicast Socket (Sender)
  # udp_unicast_sender_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
  # udp_unicast_sender_fd.bind((IP, 0))
  # udp_unicast_sender_fd.setblocking(False)
  
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
  
  
  inserts_thread = threading.Thread(target=inserts_listener)
  inserts_thread.start()
  
  proposals_thread = threading.Thread(target=proposals_listener)
  proposals_thread.start()
  
  updates_thread = threading.Thread(target=updates_listener)
  updates_thread.start()
  


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


def unicast_reliable_communication(udp_unicast_sender_fd, udp_unicast_destination_address, payload):
  while True:
    # Send to UDP Unicast
    udp_unicast_sender_fd.sendto(payload.encode(), udp_unicast_destination_address)
    readable, _, _ = select.select([udp_unicast_sender_fd], [], [], TIMEOUT)
    if len(readable) > 0:
      response, group_manager = udp_unicast_sender_fd.recvfrom(PACKET_LENGTH)
      response = response.decode()
      return
    print(f'\033[91mLost Packet {payload} to {udp_unicast_destination_address}\033[00m', )



def tcp_listener():  
  while True:
    group_manager_fd, group_manager_address = tcp_pi_fd.accept()
    with group_manager_fd:
      data = group_manager_fd.recv(PACKET_LENGTH)
      data = data.decode()
      fields = data.split(':')
      
      
      if fields[0] == 'JOIN':
        header, group_name, process_id, process_udp_unicast_address = fields

        
        for process in group_information:
          if process.group_name != group_name:
            continue
          
          process.connected_processes_mutex.acquire()
            
          # Append Process Information to Group Related List
          process.connected_processes.append({
            'process_id': process_id,
            'process_udp_address': make_tuple(process_udp_unicast_address),
            'fifo_sequence_send': 0, 
            'receive_sequence': 0,
            'leave': False,
            'pending_message_buffer': []
          })
          #print(len(process.connected_processes))
          group_manager_fd.sendall("ACK".encode())
          process.connected_processes_mutex.release()
          break
      elif fields[0] == 'LEAVE':
        header, group_name, leaving_process_id = fields
        
        for process in group_information:
          if process.group_name != group_name:
            continue
        
          process.connected_processes_mutex.acquire()
        
          for group_process in process.connected_processes[:]:
            if group_process['process_id'] != leaving_process_id:
              continue
            
            if len(group_process['pending_message_buffer']) > 0:
              group_process['leave'] = True
            
            print(f"{group_process['process_id']} has removed")
            process.connected_processes.remove(group_process)
            
            group_manager_fd.sendall("ACK".encode())
            process.connected_processes_mutex.release()
            break
           
      
        
def inserts_listener():
  while True:
    if not PENDING_INSERTS:
      continue
    
    received_request_dependencies = ''
    
    # Simulate Network Latency
    if NETWORK_LATENCY > 0:
      time.sleep(NETWORK_LATENCY)
      received_request = PENDING_INSERTS.pop(random.randint(0, len(PENDING_INSERTS) - 1))
      #print(received_request)
    else:
      # Get Received Data
      received_request = PENDING_INSERTS.pop()
      
    print(received_request)
      
    header = received_request[0]
    process_id = received_request[1]
    group_name = received_request[2]
    unstable_sequence = received_request[3]
    payload = received_request[4]
    # Dependencies
    if len(received_request) > 6:
      received_request_dependencies = received_request[-2] 
    receive_sequence = received_request[-1]
    
    
    # Check if Dependency is Satisfied
    virtual_dependencies = []
    if received_request_dependencies:
      received_request_dependencies = received_request_dependencies.split(',')
      for dependency in received_request_dependencies:
        dependency_fifo_sequence, dependency_sequence, dependency_priority, dependency_payload = dependency.split('-')
        
        # Check if Dependency is Already Satisfied (????? Might Skip)
        for process in group_information:
          if process.group_name != group_name:
            continue
          
          process.connected_processes_mutex.acquire()
          
          # Find if Process Previously Received Message
          dependency_satisfied = False
          for group_process in process.connected_processes:
            # Search if Message Already Exists
            for message in group_process['pending_message_buffer']:
              if message['total_causal_sequence'] != f'{dependency_sequence}:{dependency_priority}': # ALSO CHECK FOR PAYLOAD
                continue
              dependency_satisfied = True
            
            # Check if Message Already Received by Application
            if not dependency_satisfied:
              for message in process.delivered_messages:
                if message['total_causal_sequence'] != f'{dependency_sequence}:{dependency_priority}':
                  continue
                dependency_satisfied = True
            
          # Satisfy Unsatisfied Dependencies
          for group_process in process.connected_processes:
            if group_process['process_id'] != process_id:
              continue   
            
            # Message Dependency Message Must be Added
            if not dependency_satisfied:
              
              # Add Dependency to Prepare for Delivery
              group_process['pending_message_buffer'].append({
                'fifo_sequence_send': f'{dependency_fifo_sequence}',
                'unstable_sequence': -1,
                'total_causal_sequence': f'{dependency_sequence}:{dependency_priority}',
                'payload': dependency_payload,
                'dependencies': virtual_dependencies[:],
              })
              #print(group_process['pending_message_buffer'][-1])
              process.process_sequence = process.process_sequence + 1
            
            # Add Virtual Dependency for Message
            virtual_dependencies.append({
              'fifo_sequence_send': f'{dependency_fifo_sequence}',
              'total_causal_sequence': f'{dependency_sequence}:{dependency_priority}',
              'payload': dependency_payload
            })
              
          process.connected_processes_mutex.release()
    
    for process in group_information:
      if process.group_name != group_name:
        continue
      
      process.connected_processes_mutex.acquire()
      
      for group_process in process.connected_processes:
        if group_process['process_id'] != process_id:
          continue
        
        
        group_process['pending_message_buffer'].append({
          'fifo_sequence_send': receive_sequence,
          'unstable_sequence': int (unstable_sequence),
          'total_causal_sequence': '',
          'payload': payload,
          'dependencies': virtual_dependencies,
        })
        # print('&', group_process['pending_message_buffer'][-1])
        process.process_sequence = process.process_sequence + 1


        # Send Proposal Back to Process and Update Self
        if process.process_id != group_process['process_id']:
          # Send Proposal
          # print('Sending', f'PROPOSAL:{process.group_name}:{unstable_sequence}:{process.process_sequence}:{process.process_priority}')
          unicast_reliable_communication(
            process.udp_unicast_sender_fd, 
            group_process['process_udp_address'], 
            f'PROPOSAL:{process.group_name}:{unstable_sequence}:{process.process_sequence}:{process.process_priority}'
          )
            
      process.connected_processes_mutex.release()
      process.receive_block_semaphore.release()


def proposals_listener():
  while True:
    if PENDING_PROPOSALS.empty():
      continue
    received_request = PENDING_PROPOSALS.get()
    header, group_name, unstable_sequence, process_sequence, process_priority = received_request
    # print(received_request)
    for process in group_information:
      if process.group_name != group_name:
        continue
      
      for pending_message in process.unstable_message_buffer:
        if int (pending_message['unstable_message_sequence']) != int (unstable_sequence):
          continue
        pending_message['proposals_list'].append(f'{process_sequence}:{process_priority}')
        
        # Waiting for Proposals
        if len(pending_message['proposals_list']) != len(process.connected_processes):
          break
        
        # All Proposals Arrived
        largest_sequence = -1
        largest_priority = -1
        for proposal in pending_message['proposals_list']:
          sequence, priority = proposal.split(':')
          sequence = int (sequence)
          priority = int (priority)
          
          if (sequence > largest_sequence) or (largest_sequence == sequence and priority > largest_priority):
            largest_sequence = sequence
            largest_priority = priority
        
        process.connected_processes_mutex.acquire()
        
        for group_process in process.connected_processes:
          if process.process_id != group_process['process_id']:
            # Send Final Proposal
            unicast_reliable_communication(
              process.udp_unicast_sender_fd, 
              group_process['process_udp_address'], 
              f'UPDATE:{process.process_id}:{process.group_name}:{unstable_sequence}:{largest_sequence}:{largest_priority}'
            )
          else:
            # Feedback Loop
            for message in group_process['pending_message_buffer']:
              if int (unstable_sequence) != int (message['unstable_sequence']):
                continue
              
              message['total_causal_sequence'] = f'{largest_sequence}:{largest_priority}'

        process.connected_processes_mutex.release()


def updates_listener():
  while True:
    if PENDING_UPDATES.empty():
      continue
    received_request = PENDING_UPDATES.get()
    header, process_id, group_name, unstable_sequence, best_sequence, best_priority = received_request
    # print(received_request)
    for process in group_information:
        if process.group_name != group_name:
          continue
        
        process.connected_processes_mutex.acquire()
        
        for group_process in process.connected_processes:
          if process_id != group_process['process_id']:
            continue
          for message in group_process['pending_message_buffer']:
            if int (unstable_sequence) != int (message['unstable_sequence']):
              continue
            message['total_causal_sequence'] = f'{best_sequence}:{best_priority}'
            #print(message['total_causal_sequence'])
            
        process.connected_processes_mutex.release()
        
        
    
def udp_listener():
  while True:
    message, source_process_address = udp_unicast_receiver_fd.recvfrom(PACKET_LENGTH)
    message = message.decode()
    fields = message.split(':')
    
    # Simulating Packet Losses
    if random.randint(1, 100) > NETWORK_RELIABILITY:
      print("\033[91mDroping Packet\033[00m")
      continue
    
    # Notify Sender that Data was Received
    udp_unicast_receiver_fd.sendto('ACK'.encode(), source_process_address)
    
    #print("Send ACK")
    if fields[0] == "INSERT":
      PENDING_INSERTS.append(fields)
    elif fields[0] == "PROPOSAL":
      PENDING_PROPOSALS.put(fields)
    elif fields[0] == "UPDATE": 
      PENDING_UPDATES.put(fields)
      

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
      
      group_information.append(ServerInformation(
        virtual_file_descriptor = virtual_file_descriptor,
        group_name = group_name,
        process_id = process_id,
        process_priority = process_priority,
        process_sequence = 0,
        udp_unicast_sender_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP),
        delivered_messages = [],
        connected_processes_mutex = threading.Lock(),
        receive_block_semaphore = threading.Semaphore(0),
        group_manager_tcp_address = make_tuple(group_manager_tcp_address),
        connected_processes = [], 
        unstable_message_buffer = []
      ))

      group_information[-1].udp_unicast_sender_fd.bind((IP, 0))
      group_information[-1].udp_unicast_sender_fd.setblocking(False)
      
      group_information[-1].connected_processes_mutex.acquire()

      # Append Group Members   
      for field in fields[1:]:
        group_member_process_id, group_member_udp_address = field.split('-')
        
        # Append Received Processes Information
        group_information[-1].connected_processes.append({
          'process_id': group_member_process_id,
          'process_udp_address': make_tuple(group_member_udp_address),
          'fifo_sequence_send': 0, 
          'receive_sequence': 0,
          'pending_message_buffer': []
        })
        
        
      # Add Self on the Begining of the List
      group_information[-1].connected_processes.insert(0, {
        'process_id': process_id,
        'process_udp_address': udp_unicast_receiver_fd.getsockname(),
        'fifo_sequence_send': 0,
        'receive_sequence': 0,
        'pending_message_buffer': []
      })
      
      group_information[-1].connected_processes_mutex.release()
      break
  
  return virtual_file_descriptor


def insert_message_builder(process, payload):
  # Request: INSERT:self_process_id:self_group_name:unstable_sequence:payload:x-y-z-m1,...:fifo_sequence
  message = f'INSERT:{process.process_id}:{process.group_name}:{UNSTABLE_SEQUENCE}:{payload}'
  total_dependencies = 0
  if process.unstable_message_buffer[-1]['dependencies']:
    message = message + ':'
    for dependency in process.unstable_message_buffer[-1]['dependencies'][:-1]:
      sequence, priority = dependency['total_causal_sequence'].split(':')
      message = message + f'{dependency["fifo_sequence_send"]}-{sequence}-{priority}-{dependency["payload"]},'
      total_dependencies = total_dependencies + 1
      
    # Last Dependency
    sequence, priority = process.unstable_message_buffer[-1]['dependencies'][-1]['total_causal_sequence'].split(':')
    message = message + f'{process.unstable_message_buffer[-1]["dependencies"][-1]["fifo_sequence_send"]}-{sequence}-{priority}-{process.unstable_message_buffer[-1]["dependencies"][-1]["payload"]}'
    process.unstable_message_buffer[-1]['dependencies'][-1]
    total_dependencies = total_dependencies + 1
  
  return message, total_dependencies


def grp_send(file_descriptor, payload, payload_length):
  global UNSTABLE_SEQUENCE
  
  unicast_reliable_communication_mutex.acquire()
  for process in group_information:
    if process.virtual_file_descriptor != file_descriptor:
      continue
    
    # Add Unstable Message with Self Info (Feedback Loop)
    process.unstable_message_buffer.append({
      'unstable_message_sequence': UNSTABLE_SEQUENCE,
      'payload': payload,
      'proposals_list': [f'{process.process_sequence}:{process.process_priority}'], 
      'dependencies': process.delivered_messages[:]     
    })
    
    # Request: INSERT:self_process_id:self_group_name:unstable_sequence:payload:x-y-z-m1,...:fifo_sequence
    message, total_dependencies = insert_message_builder(process, payload)
    UNSTABLE_SEQUENCE = UNSTABLE_SEQUENCE + 1

    process.connected_processes_mutex.acquire()
    
    for group_process in process.connected_processes:
      if process.process_id != group_process['process_id']:     
        # Reliably Send Data to Processes
        unicast_reliable_communication(
          process.udp_unicast_sender_fd, 
          group_process['process_udp_address'], 
          f"{message}:{group_process['fifo_sequence_send']}"
        )
      else:
        # Feedback Loop
        group_process['pending_message_buffer'].append({
          'fifo_sequence_send': group_process['fifo_sequence_send'],
          'unstable_sequence': int (UNSTABLE_SEQUENCE) - 1,
          'total_causal_sequence': '',
          'payload': payload,
          'dependencies': process.delivered_messages[:],
        })
        
        # Total Causal Sequence
        process.process_sequence = process.process_sequence + 1
        
        # Process is Alone
        if len(process.connected_processes) < 2:
          group_process['pending_message_buffer'][-1]['total_causal_sequence'] = f'{process.process_sequence}:{process.process_priority}'
        
      group_process['fifo_sequence_send'] = group_process['fifo_sequence_send'] + 1
    
    process.connected_processes_mutex.release() 
  unicast_reliable_communication_mutex.release()
  return payload_length


def check_subset(superset, subset):
  for subset_item in subset:
    item_found = False
    for super_item in superset:
      if super_item['total_causal_sequence'] == subset_item['total_causal_sequence'] and super_item['payload'] == subset_item['payload']:
         item_found = True
    if not item_found:
      return False
  return True


# Total Causal
def tc_minimum_sequence_priority_message(process):
  smallest_sequence = sys.maxsize
  smallest_priority = sys.maxsize
  deliver_to_application_message = None
  group_process_reference = None
  
  for group_process in process.connected_processes:
    for message in group_process['pending_message_buffer']:
      if message['total_causal_sequence']:
        consensus_sequence, consensus_priority = message['total_causal_sequence'].split(':')
        # print(consensus_sequence, process.process_sequence)
        if int (process.process_sequence) < int (consensus_sequence):
          # Find Correct Sequence
          continue
        elif message['dependencies']:
          if not check_subset(superset=process.delivered_messages, subset=message['dependencies']):
            continue
        
        message_sequence, message_priority = message['total_causal_sequence'].split(':')
        message_sequence = int (message_sequence)
        message_priority = int (message_priority)
        if message_sequence < smallest_sequence or (message_sequence == smallest_sequence and message_priority < smallest_priority):
          # Find Smallest Sequence 
          smallest_sequence = message_sequence
          smallest_priority = message_priority
          deliver_to_application_message = message
          group_process_reference = group_process
  
  return deliver_to_application_message, group_process_reference    
      
# FIFO
def fifo_minimum_sequence(process):
  deliver_to_application_message = None
  group_process_reference = None
  for group_process in process.connected_processes:
    for message in group_process['pending_message_buffer'][:]:
      if message['total_causal_sequence']:
        # FIFO
        if int (message['fifo_sequence_send']) != int (group_process['receive_sequence']):
          continue
        deliver_to_application_message = message
        group_process_reference = group_process
        return deliver_to_application_message, group_process_reference
  return None, None
      
      
def grp_recv(file_descriptor, blocking, causal_total):
  while True:
    for process in group_information:
      if process.virtual_file_descriptor != file_descriptor:
        continue
      
      process.connected_processes_mutex.acquire()
      
      # Causal Total
      if causal_total:
        deliver_to_application_message, group_process_reference = tc_minimum_sequence_priority_message(process)
      else:
        deliver_to_application_message, group_process_reference = fifo_minimum_sequence(process)
        
      
        
      if not deliver_to_application_message or not group_process_reference:
        process.connected_processes_mutex.release()
        break
      
      if deliver_to_application_message not in process.delivered_messages:
        process.delivered_messages.append({
          'fifo_sequence_send': f'{deliver_to_application_message["fifo_sequence_send"]}',
          'total_causal_sequence': deliver_to_application_message['total_causal_sequence'],
          'payload': deliver_to_application_message['payload']
        })
      print(deliver_to_application_message, process.process_sequence)
      group_process_reference['pending_message_buffer'].remove(deliver_to_application_message)
      
      if not causal_total:
        group_process_reference['receive_sequence'] = group_process_reference['receive_sequence'] + 1
      
      process.connected_processes_mutex.release()
      return deliver_to_application_message['payload'], len(deliver_to_application_message['payload'])
      

      
            ############################################################################################################################################33 
          ###if group_process['leave'] and not len(group_process['pending_message_buffer']):
   
      process.connected_processes_mutex.release()
 
 
    # Handle Blocking Operations
    if not blocking:
      break
    
    # Block Execution
    for process in group_information:
      if process.virtual_file_descriptor != file_descriptor:
        continue
      
      for _ in range(process.receive_block_semaphore._value):
        process.receive_block_semaphore.acquire()
      break
      
  return None, -1
    

def grp_leave(file_descriptor):
  message = ''
  
  for process in group_information[:]:
    if process.virtual_file_descriptor != file_descriptor:
      continue
    
    process.connected_processes_mutex.acquire()
 
    
    for group_process in process.connected_processes:
      if len(group_process['pending_message_buffer']) > 0:
        print('<ERROR> Unexplored message')
        
        process.connected_processes_mutex.release()
        return -1
      
    process.connected_processes_mutex.release()
    
    leave_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    leave_fd.connect(process.group_manager_tcp_address)
    leave_fd.sendall(f'{process.virtual_file_descriptor}:{process.group_name}:{process.process_id}'.encode())

    data = leave_fd.recv(PACKET_LENGTH)
    leave_fd.close()
    data = data.decode()
    if data == "GO_THE_FUCK_AWAY":
      print(f'<SUCCESS> Leave team {process.group_name}')
      
    group_information.remove(process)
    break
  
  return 0