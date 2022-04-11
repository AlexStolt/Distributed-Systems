from process_api import *
import sys
import random

@dataclass(frozen=False, order=True)
class Groups:
  virtual_file_descriptor: int
  group_name: string
  id: string
  
SENDER_BUFFER = Queue()
RECEIVER_BUFFER = Queue()



def sender_application(fd):
  
  if not SENDER_BUFFER.empty():
     
    grp_send(fd, message, len(message))
  

def receiver_application(block, fd, iterations):
  #Wait to start 10 seconds  
  if not block:
    while True:
      source, message, length = grp_recv(fd, block, 0)
      if length < 0:
        continue
      
      print()
      print(f'\033[92m{message}\033[00m')
      
  else:
    while True:
      message, length = grp_recv(fd, block, 1)      
      print(f'\033[92m{message}\033[00m')
  

if __name__ == '__main__':
  groups = []
  if len(sys.argv) != 2:
    print("python3 <EXECUTABLE> <IP>")
    exit(-1)

  HOST_IP = sys.argv[1]
  
  api_init(HOST_IP)
 
  while True:
    print("\033[96m<<<<----Main Menu---->>>>\033[00m")
    print("conversations: ")
    for process in groups:
      print(f'{process.group_name} with id: {process.id}')

    print("\033[93mType: <j> <new group name> to join in a new group.\033[00m")
    print("\033[93mType: <i> <group> to join in a group.\033[00m")
    print("\033[93mType: <q> to exit.\033[00m")

    data = input("Type: ")

    # Shut down
    if data[0] == "q":
      if len(groups):
        print("\033[91mYou must Leave from the groups!\033[00m")
        continue
      break
    
    # Join Group
    elif data[0] == "j":
      if data[1] != " " or data[-1] == "":
        print("\033[91mWrong Input!\033[00m")
        continue
      
      id =  ''.join(random.choice(string.ascii_lowercase) for i in range(4))
      fd = grp_join(data[2:], id)
      group_name = data[2:]
      
      groups.append(Groups(
        virtual_file_descriptor = fd,
        group_name = group_name,
        id = id
      ))
      
    # Open a Group
    elif data[0] == "i":
      if data[1] != " " or data[-1] == "":
        print("\033[91mWrong Input!\033[00m")
        continue
      
      i = 0
      for process in groups:
        if process.group_name != data[2:]:
          i = i + 1
          continue
        
        group_name = process.group_name
        fd = process.virtual_file_descriptor
        id = process.id
        break
        
      if i >= len(groups):
        print("\033[91mYou haven' t join this group!\033[00m")
        continue
      
    if data[0] == "j" or data[0] == "i":
      while True:
        print(f"\033[96m<<<<<----{group_name}---->>>>>")
        print(f'id: {id}')
        print("\033[93mType: <s> <message>, to send a message.\033[00m")
        print("\033[93mType: <r> <0 or 1> (fifo or total casual) <0 or 1> (non blocking or blocking), to receive a message.\033[00m")
        print("\033[93mType: <l>, to leave from this group.\033[00m")
        print("\033[93mType: <b>, to go back.\033[00m")
        
        input_buffer = input("Type: ")
        
        #go back or leave a group
        if input_buffer[0] == "l" or input_buffer[0] == "b":
          if input_buffer[0] == "l":
            for process in groups[:]:
              if process.group_name != group_name:
                continue
                
              if not grp_leave(fd):
                print(f'<SUCCESS> Leave team {process.group_name}')
                groups.remove(process)
                break
          break  
          
        # Send message
        elif input_buffer[0] == "s":
          if input_buffer[1] != " ":
            print("\033[91mWrong Input!\033[00m")
            continue
        
          grp_send(fd, input_buffer[2:], len(input_buffer[2:]))
          
        # Receive message
        elif input_buffer[0] == "r":
          if input_buffer[1] != " " or input_buffer[3] != " ":
            print("\033[91mWrong Input!\033[00m")
            continue
          source, message, length = grp_recv(fd, int(input_buffer[-1]), int(input_buffer[-3]))
          if length < 0:
            print(f'\033[91mNo Available Messages\033[00m')
          else:
            print(f'\033[92m{source}: {message}\033[00m')
        
  api_destroy()


