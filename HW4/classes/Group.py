import threading



class Group:
  def __init__(self, environment_id, group_id: int):
    self.environment_id = environment_id
    self.group_id = group_id
    self.processes = []
    self.group_addresses = [] # A list containing all process sockets and info
    self.migration_mutex = threading.Lock()

  @property
  def is_empty(self):
    if not self.processes:
      return True
    return False

  @property
  def process_count(self):
    return len(self.processes)  


  def find_process(self, process_id: int):
    for process in self.processes:
      if process.process_id != process_id:
        continue
      return process
    return None


  def insert_group_addresses(self, group_addresses: list):
    self.group_addresses = self.group_addresses + group_addresses


  def insert_process(self, process_environment_id, process):
    # Remove duplicates if any
    for process_address in self.group_addresses[:]:
      if process_address['process_id'] != process.process_id:
        continue
      self.group_addresses.remove(process_address)
      


    self.group_addresses.append({
      'process_id': process.process_id,
      'process_address': tuple(process.udp_listener_socket.getsockname()),
      'process_environment_id': process_environment_id 
    })

    self.processes.append(process)



