from classes.Process import *
from classes.EnvironmentContainer import *
from classes.Group import *
from classes.Process import *
import sys

LOAD_BALANCE = True

if __name__ == '__main__':
  load_balancer_ip   = None
  load_balancer_port  = None
  
  if LOAD_BALANCE:
    if len(sys.argv) != 3:
      print('python3 environment.py <IP> <PORT>')
      exit(0)
    load_balancer_ip =   sys.argv[1]
    load_balancer_port =  int(sys.argv[2])


  environment_container = EnvironmentContainer(load_balance_enabled=LOAD_BALANCE, 
    load_balancer_address=(load_balancer_ip, load_balancer_port))
 

  while True:
    commands = input('Command: ')
    #commands = 'run tests/ping_pong_3/test1.ss||run tests/ping_pong_3/test2.ss||run tests/ping_pong_3/test3.ss'
    commands = commands.split('||')
    
    group = Group(environment_container.socket_info, environment_container.group_count)
    
    for command in commands:
      command_fields = command.split(' ')
      
      command_type = command_fields[0]
      # Pipe separated commands must only include 'run' commands
      if command_type != 'run' and len(commands) >= 2: 
        exit(0)
      
      elif command_type == 'run':
        program =  command_fields[1]
        
        # Handle whitespaces in strings
        arguments = []
        args = command_fields[2:]
        i = 0
        while i < len(args) -1:
          if (args[i][0] == '"' or args[i][0] == "'") and (args[i][-1] != '"' or args[i][-1] != "'"):
            argument = args[i]

            argument = args[i] + ' ' + args[i + 1]
            arguments.append(argument)
            i = i + 2
          else:
            arguments.append(args[i])
            i = i + 1
        if len(arguments):
          arguments.append(args[-1])

        print(arguments)
        file_content = EnvironmentContainer.read_file(program)
        # Insert process to group
        group.insert_process(group.environment_id, Process(program, 
          file_content, group, group.process_count, 0, {}, [], *arguments))
        
      elif command_type == 'migrate':
        group_id    = int(command_fields[1])
        process_id  = int(command_fields[2])
        dst_ip      = command_fields[3]
        dst_port    = int(command_fields[4])

        environment_container.migrate(group_id, process_id ,dst_ip, dst_port)

      elif command_type == 'list':
        environment_id = command_fields[1]
        group_id    = int(command_fields[2])
        environment_container.list_group(group_id, environment_id)
      elif command_type == 'kill':
        environment_id = command_fields[1]
        group_id    = int(command_fields[2])
        environment_container.kill_group(environment_id, group_id)

          
    # If group has at least one process then it is added
    # to the environment container
    if not group.is_empty:
      environment_container.insert_group(group, True)
      # print(environment_container.group_count)


