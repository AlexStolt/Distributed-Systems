
from os import stat
import re as regex
import threading
import time
import socket
import select
import pickle

UNBLOCKED = -1
RESET = 0
BLOCKED = 1
MIGRATED = 2

PACKET_LENGTH = 1024
TIMEOUT = 0.2
TRIES = 4

class Process:
  def __init__(self, file_path, file_content, parent_group,
      process_id: int, ip, data, received_messages, *argv): 
    
    self.file_path = file_path
    
    self.flags = RESET

    # Process ID
    self.process_id = process_id

    # Group that this process is contained in
    self.parent_group = parent_group  

    # argc and argv[]
    self.argc = len(argv) + 1
    self.argv = (self.file_path, ) + argv

    # Content of file
    self.file_content = file_content

    # File header (#SIMPLESCRIPT)
    self.header = self.file_content[0]

    # Executable instructions excluding headers 
    self.instructions = self.file_content[1:]

    # Labels contained in file
    self.labels = self.__get_labels_pos()
  
    # Instruction pointer
    self.ip = ip
  
    # Data
    self.data = data

    # Buffer of buffers used to identify messages received from processes
    self.received_messages = received_messages
    

    # Sender socket (polling)
    self.udp_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.udp_sender_socket.setblocking(False)

    # Listener socket (blocking)
    self.udp_listener_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.udp_listener_socket.bind(('', 0))


    # Listener thread to receive messages from other processes
    self.udp_listener = threading.Thread(target=self.__udp_listener_thread)
    self.udp_listener.start()

    # Locks
    self.flags_mutex = threading.Lock()

  def __udp_listener_thread(self):
    while True:
      message, process_address = self.udp_listener_socket.recvfrom(PACKET_LENGTH)
      self.flags_mutex.acquire()
      if self.flags != MIGRATED:
        message = pickle.loads(message)
        # print('***', message)
        # print('---', message)
        if message['request_type'] == 'receive':
          self.flags = UNBLOCKED
          # print('+++', self.flags)
          


        elif message not in self.received_messages and message['request_type'] == 'send': 
          self.received_messages.append(message)
          
        
        self.udp_listener_socket.sendto('ACK'.encode(), process_address)
        self.flags_mutex.release()
      else:
        self.flags_mutex.release()
        break

  # Execute n instructions from current instruction pointer
  def execute(self, n: int):
    # Check header 
    if self.header != '#SIMPLESCRIPT':
      return False,  self.ip, self.header
    
    
    for _ in range(n): 
      if self.ip < len(self.instructions):
        # Ignore process since blocked or migrated
        if self.flags == BLOCKED:
          break
        
        self.parent_group.migration_mutex.acquire()
        
        self.flags_mutex.acquire()
        if self.flags == MIGRATED:
          self.flags_mutex.release()
          self.parent_group.migration_mutex.release()
          break
        self.flags_mutex.release()

        if not self.__execute_instruction():
          # An error might have occurred, thus return the flawed
          # instruction line number and its content
          self.parent_group.migration_mutex.release()
          return False, self.ip, self.instructions[self.ip]
        
        self.parent_group.migration_mutex.release()
     
      else:
        # Program has finished
        return True, -2, None

    # Successfully finished execution of n instructions
    return True, -1, None



  # Read next instruction, check if the instruction is valid
  # and execute the instruction. After the execution the instruction
  # pointer is set appropriately.
  def __execute_instruction(self):
    instruction_fields = self.instructions[self.ip].split(' ')
    # print(self.instructions[self.ip])
    # Check if instruction starts with a label and ignore it
    if instruction_fields[0][0] == '#':
      label1 = instruction_fields.pop(0)
      if not len(instruction_fields):
        self.ip = self.ip + 1
        return True
      
    instruction_type = instruction_fields[0]
  
    if instruction_type == 'SET':
      # Check if instruction is syntactically valid
      if len(instruction_fields) != 3:
        return False

      l_var = instruction_fields[1]
      r_var = instruction_fields[2]
      
      if r_var[0] != '$':
        if r_var[0] != '"':
          self.data[l_var] = int(r_var)
        else:
          self.data[l_var] = r_var

      else:
        if r_var in self.data:
          self.data[l_var] = self.data[r_var]
        else:
          return False

      self.ip = self.ip + 1
    
    elif instruction_type == 'ADD' or instruction_type == 'SUB' or \
      instruction_type == 'MUL' or instruction_type == 'DIV' or instruction_type == 'MOD':
        
      # Check if instruction is syntactically valid
      if len(instruction_fields) != 4:
        return False

      res_var   = instruction_fields[1]
      l_var     = instruction_fields[2]
      r_var     = instruction_fields[3]

      # Result must be a variable not a literal
      if res_var[0] != '$':
        return False

      status, l_var = self.__check_get_var(l_var)
      if not status:
        return False
      
      status, r_var = self.__check_get_var(r_var)
      if not status:
        return False

      
      if instruction_type == 'ADD':
        self.data[res_var] = l_var + r_var
      
      elif instruction_type == 'SUB':
        self.data[res_var] = l_var - r_var
      
      elif instruction_type == 'MUL':
        self.data[res_var] = l_var * r_var
      
      elif instruction_type == 'DIV':
        # Division by zero
        if not r_var:
          return False
        
        self.data[res_var] = l_var / r_var
      
      elif instruction_type == 'MOD':
        self.data[res_var] = l_var % r_var

      self.ip = self.ip + 1
    
    elif instruction_type == 'BGT' or instruction_type == 'BGE' or instruction_type == 'BLT' or \
      instruction_type == 'BLE' or instruction_fields == 'BEQ':

      # Check if instruction is syntactically valid
      if len(instruction_fields) != 4:
        return False

      l_var = instruction_fields[1]
      r_var = instruction_fields[2]
      label = instruction_fields[3]


      status, l_var = self.__check_get_var(l_var)
      if not status:
        return False
      
      status, r_var = self.__check_get_var(r_var)
      if not status:
        return False

      # Check label
      if label not in self.labels:
        return False

      if instruction_type == 'BGT':
        if l_var > r_var:
          self.ip = self.labels[label] - 1
        else:
          self.ip = self.ip + 1
      
      elif instruction_type == 'BGE':
        if l_var >= r_var:
          self.ip = self.labels[label] - 1
        else:
          self.ip = self.ip + 1

      elif instruction_type == 'BLT':
        if l_var < r_var:
          self.ip = self.labels[label] - 1
        else:
          self.ip = self.ip + 1  
      
      elif instruction_type == 'BLE':
        if l_var <= r_var:
          self.ip = self.labels[label] - 1 
        else:
          self.ip = self.ip + 1

      elif instruction_type == 'BEQ':
        if l_var == r_var:
          self.ip = self.labels[label] - 1 
        else:
          self.ip = self.ip + 1
        
    elif instruction_type == 'BRA':
      # Check if instruction is syntactically valid
      if len(instruction_fields) != 2:
        return False

      label = instruction_fields[1]

      # Check label
      if label not in self.labels:
        return False

      self.ip = self.labels[label] - 1
      return True
    
    elif instruction_type == 'SLP':
      # Check if instruction is syntactically valid
      if len(instruction_fields) != 2:
        return False

      var = instruction_fields[1]
      
      status, var = self.__check_get_var(var)
      if not status:
        return False

      time.sleep(var)

      self.ip = self.ip + 1
    
    elif instruction_type == 'PRN':
      print(f"Group[{self.parent_group.group_id}] Process[{self.process_id}]:", end = ' ')
      for field in instruction_fields[1:]:
        if field[0] == '$':
          print(f"{self.data[field]}", end = ' ')
        else:
          print(field, end = ' ')

      print()
      self.ip = self.ip + 1

    elif instruction_type == 'SND':
      if len(instruction_fields) < 3:
        return False
      
      if not instruction_fields[1].isnumeric():
        return False

      destination = int(instruction_fields[1])
      
      destination_process_found = False
      destination_process_address = None
      for process in self.parent_group.group_addresses:
        if int(process['process_id']) != destination:
          continue
        
        destination_process_found = True
        destination_process_address =  process['process_address']
        
        break

      # Process destination not found 
      if not destination_process_found:
        return False


      # Return true but do not increment the ip since send must be retried
      if not destination_process_address:
        return True

      data = []
      for instruction_field in instruction_fields[2:]:
        status, var = self.__check_get_var(instruction_field, force_numeric=False)
        if not status:
          return False
        data.append(var)
      
      # Serialize data
      serialized_data = {
        "process_id": self.process_id,
        "request_type": "send",
        "data": data
      }
      serialized_data = pickle.dumps(serialized_data)


      self.udp_sender_socket.sendto(serialized_data, destination_process_address)
      for _ in range(TRIES):
        readable, _, _ = select.select([self.udp_sender_socket], [], [], TIMEOUT)

        if self.udp_sender_socket in readable:                    
          data, process_address = self.udp_sender_socket.recvfrom(PACKET_LENGTH)
          self.flags_mutex.acquire()
          # Race conditions might exist here, thus the flags must be checked
          if self.flags == UNBLOCKED:
            self.flags = RESET
          else:
            self.flags = BLOCKED

          self.flags_mutex.release()

          self.ip = self.ip + 1
          return True
                   
   
    elif instruction_type == 'RCV':
      if len(instruction_fields) < 3:
        return False
      
      if not instruction_fields[1].isnumeric():
        return False
      
      src_proc = int(instruction_fields[1])
      
      # Find if process exists
      source_process_found = False
      source_process_address = None
      for process in self.parent_group.group_addresses:
        if process['process_id'] != src_proc:
          continue
          
        source_process_found = True
        source_process_address =  process['process_address']
        break


      # Process source not found 
      if not source_process_found:
        print(src_proc, self.parent_group.group_addresses)
        return False

       # Return true but do not increment the ip since send must be retried
      if not source_process_address:
        return True


      vars = instruction_fields[2:]

      
      for received_message in self.received_messages[:]:
        if received_message['process_id'] != src_proc:
          continue
        
        # Add each variable to hash table
        for i, var in enumerate(vars):
          self.data[var] = received_message['data'][i]
        
        
        serialized_data = {
          "process_id": self.process_id,
          "request_type": "receive",
          "data": received_message['data']
        }
        serialized_data = pickle.dumps(serialized_data)

 
        self.udp_sender_socket.sendto(serialized_data, source_process_address)
        for _ in range(TRIES):
          readable, _, _ = select.select([self.udp_sender_socket], [], [], TIMEOUT)

          if self.udp_sender_socket in readable:                    
            data, process_address = self.udp_sender_socket.recvfrom(PACKET_LENGTH)
            
            # Remove message from queue
            self.received_messages.remove(received_message)
            
            self.ip = self.ip + 1
            # print('RM', received_message, self.ip)

            return True
    
      return True


    elif instruction_type == 'RET':
      self.ip = self.ip + 1
      return True
    
    else:
      return False

    return True


  # Finds the value from the hash table using the variable name as
  # a key. If the variable is a literal the integer value of the variable
  # is returned. On error False is returned.
  def __check_get_var(self, var, force_numeric=True):
    # If the variable is not defined return false
    # else set its value from data hash table
    if var[0] == '$':
      if var not in self.data: # Variable not yet defined
        return False, -1
      
      if isinstance(self.data[var], str): # Value must be integer
        return False, -1
      
      var = self.data[var]
    

    # Value might also be a literal
    else:      
      if not var.isnumeric() and force_numeric: # Value must be integer
        return False, -1 
      elif force_numeric:
        var = int(var)

    return True, var

  
  
  # Parse file to detect label occurrences. 
  # When a label is found a label - fp entry is added
  def __get_labels_pos(self):
    
    labels = {}
    for i, line in enumerate(self.file_content):
      if i < 1:
        continue

      matches = regex.search(r'^#\w+', line)
      if not matches:
        continue

      if matches.group() in labels:
        return None

      labels[matches.group()] = i

    return labels