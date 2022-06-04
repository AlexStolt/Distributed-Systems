from enum import unique
import math
from multiprocessing import connection
from os import R_OK, stat
import re
import socket
import threading
import struct
import select
import time

from pytz import common_timezones
from classes.Group import Group

from classes.Process import BLOCKED, KILLED, MIGRATED, PACKET_LENGTH, Process
import pickle

from environment import LOAD_BALANCE

N = 4
TRIES = 4
TIMEOUT = 0.2
MULTICAST_WAITING_PERIOD = 1
PACKET_LENGTH = 1024
FRAGMENT_LENGTH = 50
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 8000



class EnvironmentContainer:
  def __init__(self, load_balance_enabled=False, load_balancer_address=()):
    self.tcp_listener_fd = self.__tcp_socket_init() 
    print('Environment Address:', self.tcp_listener_fd.getsockname())
    self.groups = []
    
    # Variable used to assign group ids
    self.group_count = 0

    self.scheduler = threading.Thread(target=self.__scheduler)
    self.scheduler.start()

    self.tcp_listener = threading.Thread(target=self.__tcp_listener_thread)
    self.tcp_listener.start()

    self.load_balance_enabled = load_balance_enabled

    if self.load_balance_enabled:
      self.load_balancer_address = load_balancer_address
      self.multicast_fd = self.__multicast_socket_init()
      self.unicast_fd = self.__unicast_socket_init()
      self.multicast_listener = threading.Thread(target=self.__multicast_listener_thread)
      self.multicast_listener.start()
      self.load_balance()

  
  @property
  def socket_info(self):
    delimiter = ','
    return delimiter.join([str(value) for value in self.tcp_listener_fd.getsockname()])
    
  @property
  def load(self):
    load_counter = 0
    for group in self.groups:
      for _ in group.processes:
        load_counter = load_counter + 1
    
    return load_counter


  # Read each line of the file ignoring the empty lines
  @staticmethod
  def read_file(file_path):
    with open(file_path) as file:
      lines = file.readlines()

    # Delete '\n' from end of string
    for i in range(len(lines)):
      lines[i] = lines[i].strip()
      lines[i] = " ".join(lines[i].split())
      lines[i] = lines[i].replace('\n', '')
    
    # Delete empty lines
    return list(filter(('').__ne__, lines))
  

  def find_group(self, group_id: int, environment_id: str):
    for group in self.groups:
      if group.group_id != group_id or group.environment_id != environment_id:
        continue
      return group
    
    return None


  # Method used when the "list" command is entered to display all
  # processes running in group
  def list_group(self, group_id: int, environment_id: str):
    group = self.find_group(group_id, environment_id)
    if not group:
      return False
    
    print(f"\033[92mGROUP[{group.group_id}]:", end=' ')
    for process in group.group_addresses:
      print(f"Process[{process['process_environment_id']}][{process['process_id']}]", end=' ')
    print('\033[00m')


  # Kill a process that runs on the local environment
  def kill_local_process(self, group, process):
    process.flags = KILLED
    process.udp_listener.join()  

    # Remove process from group
    group.processes.remove(process)


  # Remove process from group addresses since the process is no longer active
  def kill_process_address_communication(self, group, process_id):
    for process_address in group.group_addresses[:]:
      if process_address['process_id'] != process_id:
        continue
      
      group.group_addresses.remove(process_address)


  # Method used when the "kill" command is entered to
  # kill a certain process from any environment
  def kill_process(self, environment_id: str, group_id: int, process_id: int):
    # Find group
    group = self.find_group(group_id, environment_id)
    if not group:
      return False
    
    serialized_data = {
      "request_type": "kill_process_request",
      "environment_id": environment_id,
      "group_id": group_id,
      "process_id": process_id
    }
    serialized_data = pickle.dumps(serialized_data)

    # Fragment Packet
    fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]

    # Update all remote environments
    unique_environments = []
    for process_address in group.group_addresses:
      if process_address['process_environment_id'] in unique_environments:
        continue

      # Add environment as an updated environment to not update again
      unique_environments.append(process_address['process_environment_id'])
      
      if process_address['process_environment_id'] != self.socket_info:
        address = process_address['process_environment_id'].split(',')
        dst_ip = address[0]
        dst_port = int(address[1])

        sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender_socket_fd.connect((dst_ip, dst_port))
        # Send all fragments (and notify the receiver that more fragments will be sent)
        for fragment in fragments[:-1]:
          serialized_data = {
            'MF': 1, # More Fragments
            'data': fragment
          }
          serialized_data = pickle.dumps(serialized_data)
          sender_socket_fd.send(serialized_data)
          
          # Receive an acknowledgement
          sender_socket_fd.recv(PACKET_LENGTH)
        
        # Send the final fragment
        serialized_data = {
          'MF': 0, # No More Fragments
          'data': fragments[-1]
        }
        serialized_data = pickle.dumps(serialized_data)
        sender_socket_fd.send(serialized_data)
        
        # Receive an acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)
        
        # Receive an acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)
      

    # Remove process communication address since process is removed
    self.kill_process_address_communication(group, process_id)
      
  
  
  def kill_group(self, environment_id: str, group_id: int):
    # Find group
    group = self.find_group(group_id, environment_id)
    if not group:
      return False
    
    group.migration_mutex.acquire() # Maybe here???

    # Kill processes running on local environment
    for process in group.processes[:]:
      self.kill_local_process(group, process)
    

    for process_address in group.group_addresses:
      if not process_address:
        continue
      # Processes that are located on different environments
      if process_address['process_environment_id'] != self.socket_info:
        address = process_address['process_environment_id'].split(',')
        dst_ip = address[0]
        dst_port = int(address[1])

        serialized_data = {
          "request_type": "kill_group_request",
          "environment_id": environment_id,
          "group_id": group_id
        }
        serialized_data = pickle.dumps(serialized_data)

        # Fragment Packet
        fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]


        sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender_socket_fd.connect((dst_ip, dst_port))

        # Send all fragments (and notify the receiver that more fragments will be sent)
        for fragment in fragments[:-1]:
          serialized_data = {
            'MF': 1, # More Fragments
            'data': fragment
          }
          serialized_data = pickle.dumps(serialized_data)
          sender_socket_fd.send(serialized_data)
          
          # Receive an acknowledgement
          sender_socket_fd.recv(PACKET_LENGTH)
        
        # Send the final fragment
        serialized_data = {
          'MF': 0, # No More Fragments
          'data': fragments[-1]
        }
        serialized_data = pickle.dumps(serialized_data)
        sender_socket_fd.send(serialized_data)
        
        # Receive an acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)

        # Receive an additional acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)

    # Completely Remove Group  
    if group in self.groups:
      self.groups.remove(group)
    
    if LOAD_BALANCE:
      # Get processes from the environments that have the most load
      received_loads, _ = self.load_balance()
      
      if not received_loads:
        group.migration_mutex.release()
        return

      # Request other environments to load balance
      for environment in received_loads:
        # Processes that are located on different environments
        if environment['environment_id'] != self.socket_info:
          address = environment['environment_id'].split(',')
          dst_ip = address[0]
          dst_port = int(address[1])

          serialized_data = {
            "request_type": "kill_migrate_request",
          }
          serialized_data = pickle.dumps(serialized_data)

          # Fragment Packet
          fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]

          while True:
            sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sender_socket_fd.connect((dst_ip, dst_port))
            
            # Send all fragments (and notify the receiver that more fragments will be sent)
            for fragment in fragments[:-1]:
              serialized_data = {
                'MF': 1, # More Fragments
                'data': fragment
              }
              serialized_data = pickle.dumps(serialized_data)
              sender_socket_fd.send(serialized_data)
              
              # Receive an acknowledgement
              sender_socket_fd.recv(PACKET_LENGTH)
            
            # Send the final fragment
            serialized_data = {
              'MF': 0, # No More Fragments
              'data': fragments[-1]
            }
            serialized_data = pickle.dumps(serialized_data)
            sender_socket_fd.send(serialized_data)
            
            # Receive an acknowledgement
            sender_socket_fd.recv(PACKET_LENGTH)
          

            # Receive an additional acknowledgement
            status = sender_socket_fd.recv(PACKET_LENGTH)
            if status != b'ACK':
              break
          
    group.migration_mutex.release()

    


  def migrate(self, environment_id: str, group_id: int, process_id: int, dst_ip: str, dst_port: int):
    group = self.find_group(group_id=group_id, environment_id=environment_id)
    if not group:
      return False
    
    process = group.find_process(process_id=process_id)
    if not process:
      return False


    group.migration_mutex.acquire()

    # Instantly mark process as migrated
    process.flags = MIGRATED

    
    # Wait for threads to terminate and remove process and group
    process.udp_listener.join()

    # Set None since data is not stable yet
    for i in range(len(group.group_addresses)):
      if group.group_addresses[i]['process_id'] != process.process_id:
        continue

      group.group_addresses[i]['process_address'] = None
      group.group_addresses[i]['process_environment_id'] = None
      break
    
    
    # Serialize data
    serialized_data = {
      "request_type": 'migrate_request',
      "current_environment_id": self.socket_info,
      "environment_id": group.environment_id,
      "group_id": group.group_id,
      "group_addresses": group.group_addresses,
      "file_path": process.file_path,
      "file_content": process.file_content,
      "process_id": process.process_id,
      "ip": process.ip,
      "data": process.data,
      "argv": process.argv,
      "received_messages": process.received_messages
    }
    
    serialized_data = pickle.dumps(serialized_data)

    # Fragment Packet
    fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]

    # Send process to client
    sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender_socket_fd.connect((dst_ip, dst_port))

    # Send all fragments (and notify the receiver that more fragments will be sent)
    for fragment in fragments[:-1]:
      serialized_data = {
        'MF': 1, # More Fragments
        'data': fragment
      }
      serialized_data = pickle.dumps(serialized_data)
      sender_socket_fd.send(serialized_data)
      
      # Receive an acknowledgement
      sender_socket_fd.recv(PACKET_LENGTH)
    
    # Send the final fragment
    serialized_data = {
      'MF': 0, # No More Fragments
      'data': fragments[-1]
    }
    serialized_data = pickle.dumps(serialized_data)
    sender_socket_fd.send(serialized_data)
    
    # Receive an acknowledgement
    sender_socket_fd.recv(PACKET_LENGTH)




    self.kill_local_process(group, process)
    if not len(group.processes):
      self.groups.remove(group)  


    # Receive an acknowledgement
    deserialized_data = b''
    serialized_data = sender_socket_fd.recv(PACKET_LENGTH)
    
    while True:
      serialized_data = pickle.loads(serialized_data)
      deserialized_data = deserialized_data + serialized_data['data']
      if not serialized_data['MF']:
        sender_socket_fd.send(b'ACK')
        break

      sender_socket_fd.send(b'ACK')
      serialized_data = sender_socket_fd.recv(PACKET_LENGTH)
      if not serialized_data:
        sender_socket_fd.send(b'ACK')
        break

    deserialized_data = pickle.loads(deserialized_data)

    group = self.find_group(deserialized_data['group_id'], deserialized_data['environment_id'])
    if not group:
      sender_socket_fd.send('ACK'.encode()) 
      return

    for process_address in group.group_addresses:
      if process_address['process_id'] != deserialized_data['process_id']:
        continue
      process_address['process_address'] = deserialized_data['process_address']
      process_address['process_environment_id'] = deserialized_data['process_environment_id']
      
    sender_socket_fd.send('ACK'.encode())

    group.migration_mutex.release()
  

  def baton_acquire_request(self, sender_socket_fd):
    # Send a Baton Acquire Request to the Coordinator
    serialized_data = {
      'request_type': 'baton_acquire_request'
    }
    serialized_data = pickle.dumps(serialized_data)

    # Request Baton
    sender_socket_fd.send(serialized_data)
    

    # Get Baton
    deserialized_data = sender_socket_fd.recv(PACKET_LENGTH)
    if deserialized_data != b'ACK':
      return False
    
    print('\033[32mBaton Acquired\033[00m')
    return True


  def baton_release_request(self, sender_socket_fd):
    # Send a Baton Acquire Request to the Coordinator
    serialized_data = {
      'request_type': 'baton_release_request'
    }
    serialized_data = pickle.dumps(serialized_data)

    # Request Baton
    sender_socket_fd.send(serialized_data)
    

    # Get Baton
    deserialized_data = sender_socket_fd.recv(PACKET_LENGTH)
    if deserialized_data != b'ACK':
      return False
    
    print('\033[32mBaton Release\033[00m')
    return True



  def load_balance(self):
    baton_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    baton_socket_fd.connect(self.load_balancer_address)
    status = self.baton_acquire_request(baton_socket_fd)
    if not status:
      return
    
    # Group just joined thus send to all environments to learn about their loads
    serialized_data = {
      'request_type': 'load_discovery_request',
      'environment_id': self.socket_info
    }
    serialized_data = pickle.dumps(serialized_data)
    self.unicast_fd.sendto(serialized_data, (MULTICAST_GROUP, MULTICAST_PORT))
    
    
    received_loads = []
    end_period = time.time() + MULTICAST_WAITING_PERIOD
    while time.time() < end_period:
      for _ in range(TRIES):
        readable, _, _ = select.select([self.unicast_fd], [], [], TIMEOUT)
        if self.unicast_fd not in readable:
          continue
        
        deserialized_data, _ = self.unicast_fd.recvfrom(PACKET_LENGTH)
        deserialized_data = pickle.loads(deserialized_data)

        received_loads.append({
          'environment_id': deserialized_data['environment_id'],
          'environment_load': deserialized_data['environment_load']
        })


    if not received_loads:
      # Send Baton Release Request
      self.baton_release_request(baton_socket_fd)
      return None, None
    

    # Compute loaded environments that need to send some of their load    
    most_loaded_environments = self.get_most_loaded_environments(received_loads)
    if not most_loaded_environments:
      # Send Baton Release Request
      self.baton_release_request(baton_socket_fd)
      return received_loads, None

    # Send to TCP sockets
    for loaded_environment in most_loaded_environments:
      address = loaded_environment['environment_id'].split(',')
      dst_ip = address[0]
      dst_port = int(address[1])

      
      for _ in range(loaded_environment['expected_processes']):
        serialized_data = {
          'request_type': 'load_reduction_request',
          'environment_id': self.socket_info
        }
        serialized_data = pickle.dumps(serialized_data)
        
        # Fragment Packet
        fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]


        # Send process to client
        sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender_socket_fd.connect((dst_ip, dst_port))
        
        for fragment in fragments[:-1]:
          serialized_data = {
            'MF': 1, # More Fragments
            'data': fragment
          }
          serialized_data = pickle.dumps(serialized_data)
          sender_socket_fd.send(serialized_data)
          
          # Receive an acknowledgement
          sender_socket_fd.recv(PACKET_LENGTH)

        # Send the final fragment
        serialized_data = {
          'MF': 0, # No More Fragments
          'data': fragments[-1]
        }
        serialized_data = pickle.dumps(serialized_data)
        sender_socket_fd.send(serialized_data)

        # Receive an acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)

        # Receive an additional acknowledgement
        sender_socket_fd.recv(PACKET_LENGTH)

    # Send Baton Release Request
    self.baton_release_request(baton_socket_fd)
    
    return received_loads, most_loaded_environments
      

  # Function that computes which environments 
  # must migrate to this environment
  def get_least_loaded_environments(self, received_loads):
    current_load = self.load
    average_load = self.load
    
    # Calculate the average load including self
    for load in received_loads:
      average_load = average_load + load['environment_load']
    
    average_load = average_load / (len(received_loads) + 1)
    upper_limit = int(math.ceil(average_load))
    lower_limit = int(average_load)

    least_loaded_environments = []
    for load in received_loads:
      if current_load > upper_limit:
        if load['environment_load'] < lower_limit:
          expected_processes = average_load - load['environment_load'] 
          if expected_processes < 1:
            expected_processes = int(expected_processes) 
          else:
            expected_processes = int(math.ceil(expected_processes))

          least_loaded_environments.append({
            'environment_id': load['environment_id'],
            'expected_processes': expected_processes
          })
          current_load = current_load - min(expected_processes, upper_limit)

    return least_loaded_environments


  # Function that computes which environments 
  # must migrate to this environment
  def get_most_loaded_environments(self, received_loads):
    average_load = self.load
    current_load = self.load
    # Calculate the average load including self
    for load in received_loads:
      average_load = average_load + load['environment_load']
    
    average_load = average_load / (len(received_loads) + 1)
    upper_limit = int(math.ceil(average_load))
    lower_limit = int(average_load)
    
    most_loaded_environments = []
    for load in received_loads:
      if current_load < lower_limit:
        if load['environment_load'] > upper_limit:
          expected_processes = load['environment_load'] - average_load
          if expected_processes < 1:
            expected_processes = int(math.ceil(expected_processes))
          else:
            expected_processes = int(expected_processes)

          most_loaded_environments.append({
            'environment_id': load['environment_id'],
            'expected_processes': min(expected_processes, lower_limit)
          })
          current_load = current_load + min(expected_processes, lower_limit)
    
    return most_loaded_environments


  def __multicast_listener_thread(self):
    
    while True:
      for _ in range(TRIES):
        readable, _, _ = select.select([self.multicast_fd], [], [], TIMEOUT)
        
        if self.multicast_fd in readable:
          deserialized_data, address = self.multicast_fd.recvfrom(PACKET_LENGTH)
          deserialized_data = pickle.loads(deserialized_data)

          if deserialized_data['request_type'] == 'load_discovery_request':
            # Ignore messages from self
            if deserialized_data['environment_id'] == self.socket_info:
              continue

            # Get current environment's load 
            serialized_data = {
              'request_type': 'load_discovery_response',
              'environment_id': self.socket_info,
              'environment_load': self.load
            }
            serialized_data = pickle.dumps(serialized_data)

            self.multicast_fd.sendto(serialized_data, address)
          
           
  def __tcp_listener_thread(self):
    while True:
      connection, address = self.tcp_listener_fd.accept()
      with connection:
        deserialized_data = b''
        serialized_data = connection.recv(PACKET_LENGTH)
        if not serialized_data:
            break

        
       
        while True:
          serialized_data = pickle.loads(serialized_data)
          deserialized_data = deserialized_data + serialized_data['data']
          if not serialized_data['MF']:
            connection.send(b'ACK')
            break

          connection.send(b'ACK')
          serialized_data = connection.recv(PACKET_LENGTH)
          if not serialized_data:
            connection.send(b'ACK')
            break

        deserialized_data = pickle.loads(deserialized_data)


        # Migration response
        if deserialized_data['request_type'] == 'migrate_response':
          group = self.find_group(deserialized_data['group_id'], deserialized_data['environment_id'])
          if not group:
            connection.send('ACK'.encode())
            continue 

          for process_address in group.group_addresses:
            if process_address['process_id'] != deserialized_data['process_id']:
              continue
            process_address['process_address'] = deserialized_data['process_address']
            process_address['process_environment_id'] = deserialized_data['process_environment_id']
            
          
          connection.send('ACK'.encode())
          
          continue
        
        # Migration request
        elif deserialized_data['request_type'] == 'migrate_request':
          # Check if group already exists and if not create a new one
          group_exists = False
          for group in self.groups:
            if group.group_id != deserialized_data['group_id'] or group.environment_id != deserialized_data['environment_id']:
              continue
            
            group_exists = True
            process = Process(
              deserialized_data['file_path'], deserialized_data['file_content'], group, deserialized_data['process_id'], 
              deserialized_data['ip'], deserialized_data['data'], deserialized_data['received_messages'])
            
            group.insert_process(self.socket_info, process)
            break
          
          
    
          # Group does not exist thus create a group
          if not group_exists:
            # Also inserts self environment 
            group = Group(deserialized_data['environment_id'], deserialized_data['group_id'])

            # Create a process
            process = Process(
              deserialized_data['file_path'], deserialized_data['file_content'], 
              group, deserialized_data['process_id'], deserialized_data['ip'], 
              deserialized_data['data'], deserialized_data['received_messages'])

            
            group.insert_group_addresses(deserialized_data['group_addresses'])
            group.insert_process(self.socket_info, process)
            
            self.insert_group(group, False)

          # connection.send('ACK'.encode())
          
          # Reply to sender with the new socket that the process has
          serialized_data = {
            "request_type": 'migrate_response',
            "environment_id": group.environment_id,
            "group_id": group.group_id,
            "process_id": process.process_id,
            "process_address": process.udp_listener_socket.getsockname(),
            "process_environment_id": self.socket_info
          }
          
          serialized_data = pickle.dumps(serialized_data)

          # Fragment Packet
          fragments = [serialized_data[i:i+FRAGMENT_LENGTH] for i in range(0, len(serialized_data), FRAGMENT_LENGTH)]

          # Send to all TCP environments (Only Once)
          unique_environments = []
          for process_address in group.group_addresses:
            if process_address['process_environment_id'] in unique_environments:
              continue
              
            # Should not send back to original sender immediately
            # This will be handled later to keep the environment blocked
            if process_address['process_environment_id'] == deserialized_data['current_environment_id']:
              continue
            
            # Add environment as an updated environment to not update again
            unique_environments.append(process_address['process_environment_id'])
            
            if process_address['process_environment_id'] != self.socket_info:
              address = process_address['process_environment_id'].split(',')
              dst_ip = address[0]
              dst_port = int(address[1])


              # Send process to client
              sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
              sender_socket_fd.connect((dst_ip, dst_port))
              
              for fragment in fragments[:-1]:
                serialized_data = {
                  'MF': 1, # More Fragments
                  'data': fragment
                }
                serialized_data = pickle.dumps(serialized_data)
                sender_socket_fd.send(serialized_data)
                
                # Receive an acknowledgement
                sender_socket_fd.recv(PACKET_LENGTH)
              
              # Send the final fragment
              serialized_data = {
                'MF': 0, # No More Fragments
                'data': fragments[-1]
              }
              serialized_data = pickle.dumps(serialized_data)
              sender_socket_fd.send(serialized_data)
              
              # Receive an acknowledgement
              sender_socket_fd.recv(PACKET_LENGTH)

              
              # Receive an additional ACK
              sender_socket_fd.recv(PACKET_LENGTH)
          

          # Send back to original environment (ACK)
          for fragment in fragments[:-1]:
            serialized_data = {
              'MF': 1, # More Fragments
              'data': fragment
            }
            serialized_data = pickle.dumps(serialized_data)
            connection.send(serialized_data)
            
            # Receive an acknowledgement
            connection.recv(PACKET_LENGTH)
          
          # Send the final fragment
          serialized_data = {
            'MF': 0, # No More Fragments
            'data': fragments[-1]
          }
          serialized_data = pickle.dumps(serialized_data)
          connection.send(serialized_data)
          
          # Receive an acknowledgement
          connection.recv(PACKET_LENGTH)

          
          # Receive an additional ACK
          connection.recv(PACKET_LENGTH)


        elif deserialized_data['request_type'] == 'kill_process_request':
          group = self.find_group(deserialized_data['group_id'],  deserialized_data['environment_id'])
          if not group:
            connection.send('ACK'.encode())
            continue
          
          self.kill_process_address_communication(group, deserialized_data['process_id'])
          connection.send('ACK'.encode())
        
        # Kill Group Request
        elif deserialized_data['request_type'] == 'kill_group_request':
          group = self.find_group(deserialized_data['group_id'], deserialized_data['environment_id'])
          if group:  
            for process in group.processes[:]:
              self.kill_local_process(group, process)
          
          connection.send('ACK'.encode())
        
        # Load Reduction Request
        elif deserialized_data['request_type'] == 'load_reduction_request':
          address = deserialized_data['environment_id'].split(',')
          dst_ip = address[0]
          dst_port = int(address[1])
          
          environment_id, group_id, process_id = self.lra_process()
          if not environment_id or group_id < 0 or process_id < 0:
            break
          
          self.migrate(environment_id, group_id, process_id, dst_ip, dst_port)
          
          
          connection.send('ACK'.encode())

        # Migrate after Kill Request
        elif deserialized_data['request_type'] == 'kill_migrate_request':

          serialized_data = {
            'request_type': 'load_discovery_request',
            'environment_id': self.socket_info
          }
          serialized_data = pickle.dumps(serialized_data)
          self.unicast_fd.sendto(serialized_data, (MULTICAST_GROUP, MULTICAST_PORT))
          
          received_loads = []
          end_period = time.time() + MULTICAST_WAITING_PERIOD
          while time.time() < end_period:
            for _ in range(TRIES):
              readable, _, _ = select.select([self.unicast_fd], [], [], TIMEOUT)
              if self.unicast_fd not in readable:
                continue
              
              deserialized_data, _ = self.unicast_fd.recvfrom(PACKET_LENGTH)
              deserialized_data = pickle.loads(deserialized_data)

              received_loads.append({
                'environment_id': deserialized_data['environment_id'],
                'environment_load': deserialized_data['environment_load']
              })

          if not received_loads:
            connection.send('NACK'.encode())
            continue
          
          # Compute loaded environments that need to receive some of current load    
          least_loaded_environments = self.get_least_loaded_environments(received_loads)
          if not least_loaded_environments:
            connection.send('NACK'.encode())
            continue
          


          sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sender_socket_fd.connect(self.load_balancer_address)
          status = self.baton_acquire_request(sender_socket_fd=sender_socket_fd)
          if not status:
            return

          
          address = least_loaded_environments[0]['environment_id'].split(',')
          dst_ip = address[0]
          dst_port = int(address[1])
          
          environment_id, group_id, process_id = self.lra_process()
          if not environment_id or group_id < 0 or process_id < 0:
            break
          
          self.migrate(environment_id, group_id, process_id, dst_ip, dst_port)

          connection.send('ACK'.encode())
          
          # Send Baton Release Request
          self.baton_release_request(sender_socket_fd)
          
          



  # Function that returns the least recently appended process_id
  def lra_process(self):
    try:
      return self.groups[0].environment_id, self.groups[0].group_id, self.groups[0].processes[0].process_id
    except:
      return None, -1, -1


  def __scheduler(self):
    while True:
      for i, group in enumerate(self.groups[:]):
        for process in group.processes:
          # Ignore process since blocked or migrated
          if process.flags == BLOCKED or process.flags == MIGRATED:
            continue
          
          status, index, instruction = process.execute(N)

          # Error has occurred
          if not status:
            print(f'Group[{group.group_id}] removed due to process {process.process_id} error in line {index}: {instruction}')
            self.kill_group(group.environment_id, group.group_id)
            break
          
          # N instruction were successfully executed
          elif index == -1:
            continue
          
          # If process has finished remove process
          elif index == -2:
            self.kill_local_process(self.groups[i], process)
            self.kill_process(self.groups[i].environment_id, self.groups[i].group_id, process.process_id)
            
            # If group is empty remove group
            if not len(self.groups[i].processes):
              print(f'Group[{group.group_id}] removed since all processes finished')
              self.groups.remove(self.groups[i])
            if LOAD_BALANCE:
              # Try to load balance again since processes are finished
              self.load_balance()

  def insert_group(self, group, force_load_balancing: bool):
    if group.is_empty:
      return
    
    self.groups.append(group)
    
    if force_load_balancing:
      self.group_count = self.group_count + 1


    # Load balancing is disabled
    if not self.load_balance_enabled or not force_load_balancing:
      return

    sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender_socket_fd.connect(self.load_balancer_address)
    status = self.baton_acquire_request(sender_socket_fd=sender_socket_fd)
    if not status:
      return


    # Group just joined thus send to all environments to learn about their loads
    serialized_data = {
      'request_type': 'load_discovery_request',
      'environment_id': self.socket_info
    }
    serialized_data = pickle.dumps(serialized_data)
    self.unicast_fd.sendto(serialized_data, (MULTICAST_GROUP, MULTICAST_PORT))
    
    received_loads = []

    end_period = time.time() + MULTICAST_WAITING_PERIOD
    while time.time() < end_period:
      for _ in range(TRIES):
        readable, _, _ = select.select([self.unicast_fd], [], [], TIMEOUT)
        if self.unicast_fd not in readable:
          continue
        
        deserialized_data, _ = self.unicast_fd.recvfrom(PACKET_LENGTH)
        deserialized_data = pickle.loads(deserialized_data)

        received_loads.append({
          'environment_id': deserialized_data['environment_id'],
          'environment_load': deserialized_data['environment_load']
        })

    if not received_loads:
      # Send Baton Release Request
      self.baton_release_request(sender_socket_fd)
      return

    
    # Compute loaded environments that need to receive some of current load    
    least_loaded_environments = self.get_least_loaded_environments(received_loads)
    if not least_loaded_environments:
      # Send Baton Release Request
      self.baton_release_request(sender_socket_fd)
      return
    

    for least_loaded_environment in least_loaded_environments:
      address = least_loaded_environment['environment_id'].split(',')
      dst_ip = address[0]
      dst_port = int(address[1])


      for _ in range(least_loaded_environment['expected_processes']):
        environment_id, group_id, process_id = self.lra_process()
        if not environment_id or group_id < 0 or process_id < 0:
          break
        
        self.migrate(environment_id, group_id, process_id, dst_ip, dst_port)

    # Send Baton Release Request
    self.baton_release_request(sender_socket_fd)
    

  def __unicast_socket_init(self):
    unicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unicast_fd.setblocking(False)

    return unicast_fd

  def __multicast_socket_init(self):
    multicast_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    multicast_fd.bind((MULTICAST_GROUP, MULTICAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    multicast_fd.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    multicast_fd.setblocking(False)

    return multicast_fd


  def __tcp_socket_init(self, address: str = '', port: int = 0):
    tcp_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_fd.bind((address, port))
    tcp_fd.listen()

    return tcp_fd