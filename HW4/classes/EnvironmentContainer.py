from multiprocessing import connection
import socket
import threading
import time
from traceback import print_tb
from classes.Group import Group

from classes.Process import BLOCKED, MIGRATED, PACKET_LENGTH, Process
import pickle

N = 4

class EnvironmentContainer:
  def __init__(self):
    self.tcp_listener_fd = self.__socket_init() 
    print(self.tcp_listener_fd.getsockname())
    
    self.groups = []

    self.scheduler = threading.Thread(target=self.__scheduler)
    self.scheduler.start()

    self.tcp_listener = threading.Thread(target=self.__tcp_listener_thread)
    self.tcp_listener.start()


  @property
  def group_count(self):
    return len(self.groups)

  @property
  def socket_info(self):
    delimiter = ','
    return delimiter.join([str(value) for value in self.tcp_listener_fd.getsockname()])
    


  # Read each line of the file ignoring the empty lines
  @staticmethod
  def read_file(file_path):
    with open(file_path) as file:
      lines = file.readlines()
    
    # Delete '\n' from end of string
    for i in range(len(lines)):
      lines[i] = lines[i].replace('\n', '')
    
    # Delete empty lines
    return list(filter(('').__ne__, lines))
  


  def find_group(self, group_id: int):
    for group in self.groups:
      if group.group_id != group_id:
        continue
      return group
    
    return None

  
  def group_list(self, group_id: int):
    group = self.find_group(group_id)

    print(f"GROUP[{group.group_id}]:")
    for process in group.group_addresses:
      print(f"Process[{process['process_id']}]")


  def migrate(self, group_id: int, process_id: int, dst_ip: str, dst_port: int):
    group = self.find_group(group_id=group_id)
    if not group:
      return False
    
    process = group.find_process(process_id=process_id)
    if not process:
      return False

    

    group.migration_mutex.acquire()
    print('MIGRATING NOW')

    # Instantly mark process as migrated
    process.flags_mutex.acquire()
    process.flags = MIGRATED
    process.flags_mutex.release()
    
    # sent_group_addresses = group.group_addresses[:]
    for i in range(len(group.group_addresses)):
      if group.group_addresses[i]['process_id'] != process.process_id:
        continue

      group.group_addresses[i]['process_address'] = None
      # sent_group_addresses.remove(group.group_addresses[i])
      break
    
    # Group will be removed thus remove self from list
    if len(group.processes) == 1:
      group.group_environments.remove(self.socket_info)
    
    # Serialize data
    serialized_data = {
      "request_type": 'migrate_request',
      "environment_id": group.environment_id,
      "group_id": group.group_id,
      "group_environments": group.group_environments,
      "group_addresses": group.group_addresses,
      "file_path": process.file_path,
      "file_content": process.file_content,
      "process_id": process.process_id,
      "ip": process.ip,
      "data": process.data,
      "argv": process.argv,
      "received_messages": process.received_messages
    }
    # print('@@@', process.received_messages)
    serialized_data = pickle.dumps(serialized_data)

    # Send process to client
    sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender_socket_fd.connect((dst_ip, dst_port))
    sender_socket_fd.send(serialized_data)
    
    # Receive an acknowledgement
    sender_socket_fd.recv(PACKET_LENGTH)
    
    # Remove process and group
    group.processes.remove(process)
    if not len(group.processes):
      self.groups.remove(group)  

    group.migration_mutex.release()
    


  def __tcp_listener_thread(self):
    while True:
      connection, address = self.tcp_listener_fd.accept()
      with connection:
        data = connection.recv(PACKET_LENGTH)
        if not data:
            break
        
        deserialized_data = pickle.loads(data)
        
        # print('+++', deserialized_data)
        if deserialized_data['request_type'] != 'migrate_request':
          print(deserialized_data)
          received_group = self.find_group(deserialized_data['group_id'])
          if not received_group:
            connection.send('ACK'.encode())
            continue 

          # received_group.migration_mutex.acquire()
          for group_iterator in received_group.group_addresses:
            if group_iterator['process_id'] != deserialized_data['process_id']:
              continue
            group_iterator['process_address'] = deserialized_data['process_address']
            # print('&&&&', group_iterator)
          
          received_group.group_environments = deserialized_data['migrated_environments']
          print(received_group.group_environments)
          connection.send('ACK'.encode())
          # print(received_group.group_environments)
          # received_group.migration_mutex.release()
          continue


        # Check if group already exists and if not create a new one
        group_exists = False
        for group in self.groups:
          if group.group_id != deserialized_data['group_id'] or group.environment_id != deserialized_data['environment_id']:
            continue
          
          group_exists = True
          process = Process(
            deserialized_data['file_path'], deserialized_data['file_content'], group, deserialized_data['process_id'], 
            deserialized_data['ip'], deserialized_data['data'], deserialized_data['received_messages'], deserialized_data['argv'])
          
          group.group_environments = deserialized_data['group_environments']
          group.insert_process(process)
          break

        
        # Group does not exist thus create a group
        if not group_exists:
          # Also inserts self environment 
          group = Group(deserialized_data['environment_id'], deserialized_data['group_id'])
          # Insert environments remaining environments
          for environment in deserialized_data['group_environments']:
            if environment not in group.group_environments:
              group.insert_environment(environment)
          
          # Insert new environment (self)
          group.insert_environment(self.socket_info)

          # Create a process
          process = Process(
            deserialized_data['file_path'], deserialized_data['file_content'], group, deserialized_data['process_id'], 
            deserialized_data['ip'], deserialized_data['data'], deserialized_data['received_messages'], deserialized_data['argv'])

          
          group.insert_group_addresses(deserialized_data['group_addresses'])
          group.insert_process(process)
          
          self.insert_group(group)

        connection.send('ACK'.encode())
        
        # Reply to sender with the new socket that the process has
        serialized_data = {
          "request_type": 'migrate_response',
          "environment_id": group.environment_id,
          "group_id": group.group_id,
          "migrated_environments": group.group_environments,
          "process_id": process.process_id,
          "process_address": process.udp_listener_socket.getsockname()
        }
        # print('---', serialized_data)
        serialized_data = pickle.dumps(serialized_data)

        # Send to all TCP environments
        for environment in group.group_environments:
          # print(environment, self.socket_info)
          if environment != self.socket_info:
            address = environment.split(',')
            dst_ip = address[0]
            dst_port = int(address[1])


            # Send process to client
            sender_socket_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sender_socket_fd.connect((dst_ip, dst_port))
            sender_socket_fd.send(serialized_data)
            
            # Receive new socket address
            acknowledgement = sender_socket_fd.recv(PACKET_LENGTH)
            # print(acknowledgement)
      # group.migration_mutex.release()
      # connection.send(serialized_data)
        

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
            self.groups.remove(group)
            break
          
          # N instruction were successfully executed
          elif index == -1:
            continue
          
          # If process has finished remove process
          elif index == -2:
            self.groups[i].processes.remove(process)
            
            # If group is empty remove group
            if not len(self.groups[i].processes):
              print(f'Group[{group.group_id}] removed since all processes finished')
              self.groups.remove(self.groups[i])

  def insert_group(self, group):
    if not group.is_empty:
      self.groups.append(group)

  
  

  def __socket_init(self, address: str = '', port: int = 0):
    fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fd.bind((address, port))
    fd.listen()

    return fd