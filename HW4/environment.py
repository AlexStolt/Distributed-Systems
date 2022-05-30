from classes.Process import *
from classes.EnvironmentContainer import *
from classes.Group import *
from classes.Process import *

if __name__ == '__main__':
  environment_container = EnvironmentContainer()
 
  while True:

    commands = input('Command: ')
    #commands = 'run tests/ping_pong_3/test1.ss||run tests/ping_pong_3/test2.ss||run tests/ping_pong_3/test3.ss'
    commands = commands.split('||')
    
    group = Group(environment_container.socket_info, environment_container.group_count)
    group.insert_environment(environment_container.socket_info)
    
    for command in commands:
      command_fields = command.split(' ')
      
      command_type = command_fields[0]
      # Pipe separated commands must only include 'run' commands
      if command_type != 'run' and len(commands) >= 2: 
        exit(0)
      
      elif command_type == 'run':
        program =  command_fields[1]
        args = command_fields[2:]
        
        file_content = EnvironmentContainer.read_file(program)
        # Insert process to group
        group.insert_process(
          Process(program, file_content, group, group.process_count, 0, {}, [], *args))
        
      elif command_type == 'migrate':
        group_id    = int(command_fields[1])
        process_id  = int(command_fields[2])
        dst_ip      = command_fields[3]
        dst_port    = int(command_fields[4])

        environment_container.migrate(group_id, process_id ,dst_ip, dst_port)

      elif command_type == 'list':
        group_id    = int(command_fields[1])
        environment_container.group_list(group_id)

    # If group has at least one process then it is added
    # to the environment container
    if not group.is_empty:
      environment_container.insert_group(group)
      # print(environment_container.group_count)


