#include "nfs.h"


void *udp_requests_listener(void *arguments){
  char received_request[SIZE];
  int received_request_length = -1;

  request_t *request;
  
  while (1) {
    request = (request_t *) malloc(sizeof(request_t));
    if(!request){
      exit(EXIT_FAILURE);
    }
    
    memset(received_request, 0, SIZE * sizeof(char));  
    memset(&request->source, 0, sizeof(struct sockaddr));
    memset(&request->address_length, 0, sizeof(socklen_t));
    request->address_length = sizeof(struct sockaddr);


    // Receive Data
    received_request_length = recvfrom(unicast_socket_fd, received_request, SIZE * sizeof(char), 0, &request->source, &request->address_length);
    if(received_request_length < 0){
      continue;
    }

    // Parse Request and Break it to Fields
    request->fields = parse_request(received_request, &request->fields_length);
    if(!request->fields){
      continue;
    }

    append_request(requests_list, request);
  }
  
  return NULL;
}



int lookup_handler(char *file_path, int flags){
  file_t *file;
  int fd;
  int file_id;

  file_id = -1;
  for(int i = 0; i < file_container->length; i++){
    if(!file_container->files[i]){
      continue;
    }
    
    if(!strcmp(file_container->files[i]->file_path, file_path)){
      file_id = file_container->files[i]->file_id;
      break;
    }
  }

  if(file_id < 0){
    fd = open(file_path, flags);
    if(fd < 0){
      return -1;
    }

    file = (file_t *) malloc(sizeof(file_t));
    if(!file){
      exit(EXIT_FAILURE);
    }

    file_id = file_container->current_id;

    strcpy(file->file_path, file_path);
    file->file_id = file_container->current_id;
    file->file_fd = fd;
    file->t_modified = 0;

    file_container->files[file_container->length] = file;
    file_container->length++;
    file_container->current_id++;
  }

  return file_id;
}



void *udp_requests_handler(void *arguments){
  request_t *selected_request;
  char *request_type;
  char *file_path;
  int flags;
  int file_id;
  char file_id_string[SIZE]; 
  
  char *serialized_response;
  
  
  // Used for Read Operations
  int position;
  int length;
  int file_position;
  char t_modified_string[SIZE];
  char *read_buffer;
  ssize_t bytes_read;

  field_t response_fields[SIZE];
  int fields_length;
  int response_length;

  while (1){
    // Select a Pending Request
    selected_request = pop_request(requests_list);
    
#ifdef DEBUG
    print_request(selected_request);
#endif

    request_type = selected_request->fields[0].field; 
    if(!strcmp(request_type, "LOOKUP_REQ")){
      file_path = selected_request->fields[1].field;
      flags = atoi(selected_request->fields[2].field);

      file_id = lookup_handler(file_path, flags);

      // Set Response
      if(file_id < 0){
        // Response Type
        strcpy(response_fields[0].field, "LOOKUP_RES");
        response_fields[0].length = strlen(response_fields[0].field);

        // Response Status
        strcpy(response_fields[1].field, "NACK");
        response_fields[1].length = strlen(response_fields[1].field);
        
        // Total Fields
        fields_length = 2;
      }
      else {
        // Response Type
        strcpy(response_fields[0].field, "LOOKUP_RES");
        response_fields[0].length = strlen(response_fields[0].field);
        
        // Response Status
        strcpy(response_fields[1].field, "ACK");
        response_fields[1].length = strlen(response_fields[1].field);

        // File Path
        strcpy(response_fields[2].field, file_path);
        response_fields[2].length = strlen(response_fields[2].field);

        // File ID
        sprintf(file_id_string, "%d", file_id);
        strcpy(response_fields[3].field, file_id_string);
        response_fields[3].length = strlen(response_fields[3].field);

        // Total Fields
        fields_length = 4;
      }

      // Serialize Response from Fields
      serialized_response = serialize_request(response_fields, fields_length, &response_length);
      
      // Send Response
      sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
    }
    else if(!strcmp(request_type, "READ_REQ")){
      file_id = atoi(selected_request->fields[1].field);
      position = atoi(selected_request->fields[2].field);
      length = atoi(selected_request->fields[3].field);

      // Allocate Memory for the Read Buffer based on the Length
      read_buffer = (char *) calloc(length, sizeof(char));
      if(!read_buffer){
        continue;
      }


      // Search for File FD using its ID
      file_position = -1;
      for(int i = 0; i < file_container->length; i++){
        if(!file_container->files[i]){
          continue;
        }
        
        if(file_container->files[i]->file_id != file_id){
          continue;
        }

        file_position = i;
        break;
      }



      // file_container->files[file_position]
      lseek(file_container->files[file_position]->file_fd, position, SEEK_SET);
      memset(read_buffer, 0, length * sizeof(char));
      bytes_read = read(file_container->files[file_position]->file_fd, read_buffer, length);

      // Response Type
      strcpy(response_fields[0].field, "READ_RES");
      response_fields[0].length = strlen(response_fields[0].field);

      // T_MODIFIED
      sprintf(t_modified_string, "%d", file_container->files[file_position]->t_modified);
      strcpy(response_fields[1].field, t_modified_string);
      response_fields[1].length = strlen(response_fields[1].field);
      
      // Response Buffer
      strncpy(response_fields[2].field, read_buffer, bytes_read);
      response_fields[2].length = bytes_read;

      // Total Fields
      fields_length = 3;
      
      // Serialize Response from Fields
      serialized_response = serialize_request(response_fields, fields_length, &response_length);
      
      // Send Response
      sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
    }

  }
}


void nfs_server_init(){
  pthread_t udp_requests_listener_daemon;
  pthread_t udp_requests_handler_daemon;
  requests_list = requests_list_init();
  unicast_socket_fd = _unicast_socket_init();
  file_container = files_init();


  if(pthread_create(&udp_requests_listener_daemon, NULL, udp_requests_listener, NULL) != 0){
    exit(EXIT_FAILURE);
  }

  if(pthread_create(&udp_requests_handler_daemon, NULL, udp_requests_handler, NULL) != 0){
    exit(EXIT_FAILURE);
  }


  pthread_join(udp_requests_listener_daemon, NULL);
  pthread_join(udp_requests_handler_daemon, NULL);
}
