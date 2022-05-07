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


void lookup_handler(request_t *selected_request){
  file_t *file;
  char *file_path;
  int fd, flags, file_id;
  char file_id_string[SIZE]; 
  
  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;

  file_path   = selected_request->fields[1].field;
  flags       = atoi(selected_request->fields[2].field);


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
      return;
    }

    file = (file_t *) malloc(sizeof(file_t));
    if(!file){
      exit(EXIT_FAILURE);
    }

    file_id = file_container->current_id;

    strcpy(file->file_path, file_path);
    file->file_id = file_container->current_id;
    file->file_fd = fd;
    memset(file->blocks, 0, SIZE * sizeof(block_t *));

    file_container->files[file_container->length] = file;
    file_container->length++;
    file_container->current_id++;
  }

  
  // Response Type
  strcpy(response_fields[0].field, "LOOKUP_RES");
  response_fields[0].length = strlen(response_fields[0].field);
      
  // Set Response
  if(file_id < 0){
    // Response Status
    strcpy(response_fields[1].field, "NACK");
    response_fields[1].length = strlen(response_fields[1].field);
    
    // Total Fields
    fields_length = 2;
  }
  else {
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


void read_handler(request_t *selected_request){
  int file_id, block_start, block_size, t_modified;
  int file_index;
  char *read_buffer;
  ssize_t bytes_read;
  block_t *selected_block;
  bool block_modified;
  char t_modified_string[SIZE];

  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;

  // Get Request Fields
  file_id     = atoi(selected_request->fields[1].field);
  block_start = atoi(selected_request->fields[2].field);
  block_size  = atoi(selected_request->fields[3].field);
  t_modified  = atoi(selected_request->fields[4].field);

  printf("%d %d %d %d\n", file_id, block_start, block_size, t_modified);
  fflush(stdout);
  
  // Allocate Memory for the Read Buffer based on the Length
  read_buffer = (char *) calloc(block_size, sizeof(char));
  if(!read_buffer){
    return;
  }
  memset(read_buffer, 0, block_size * sizeof(char));

  // Search for File FD using its ID
  file_index = get_fd_by_id(file_container, file_id);
  if(file_index < 0){
    return;
  }

  // Check if block was modified
  block_modified = false;
  selected_block = get_block_from_file(file_container->files[file_index], block_start);
  if(selected_block != NULL){
    if (t_modified < selected_block->t_modified){
        block_modified = true;
    }
  }

  // Response Type
  strcpy(response_fields[0].field, "READ_RES");
  response_fields[0].length = strlen(response_fields[0].field);
  
  if((!selected_block && t_modified < 0) || block_modified){
    lseek(file_container->files[file_index]->file_fd, block_start, SEEK_SET);
    bytes_read = read(file_container->files[file_index]->file_fd, read_buffer, block_size);
    
    // Read Status
    if(bytes_read < 0){
      strcpy(response_fields[1].field, "NACK");
    }
    else {
      strcpy(response_fields[1].field, "ACK");
    }
    response_fields[1].length = strlen(response_fields[1].field);

    // Block Modified
    if(!selected_block){
      sprintf(t_modified_string, "0");
    }
    else {
      sprintf(t_modified_string, "%d", selected_block->t_modified);
    }
    strcpy(response_fields[2].field, t_modified_string);
    response_fields[2].length = strlen(response_fields[2].field);
    
    // Response Buffer
    strncpy(response_fields[3].field, read_buffer, bytes_read); // ********* BUG
    response_fields[3].length = bytes_read;

    // Total Fields
    fields_length = 4;
  }
  else if(!block_modified){
    strcpy(response_fields[1].field, "ACK");
    response_fields[1].length = strlen(response_fields[1].field);

    fields_length = 2;
  }

  // Serialize Response from Fields
  serialized_response = serialize_request(response_fields, fields_length, &response_length);
  
  // Send Response
  sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);

  free(read_buffer);
}


void write_handler(request_t *selected_request){
  int file_id, fp_position, bytes_to_write, block_size;
  char *buffer_to_write;
  char *read_buffer;
  int file_index;
  int bytes_written;
  int bytes_read;
  int t_modified; 
  block_t *selected_block;
  int start;
  int empty_block_position;
  char t_modified_string[SIZE];

  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;


  // Request Fields
  file_id         = atoi(selected_request->fields[1].field);
  fp_position     = atoi(selected_request->fields[2].field);
  bytes_to_write  = atoi(selected_request->fields[3].field);
  buffer_to_write = selected_request->fields[4].field;
  block_size      = atoi(selected_request->fields[5].field);
  

  file_index = get_fd_by_id(file_container, file_id);
  if(file_index < 0){
    return;
  }

  


  lseek(file_container->files[file_index]->file_fd, fp_position, SEEK_SET);
  bytes_written = write(file_container->files[file_index]->file_fd, buffer_to_write, bytes_to_write);
  if(bytes_written < 0){
    // Send Error
  }

  // Allocate Memory for the Read Buffer based on the Length
  read_buffer = (char *) calloc(block_size, sizeof(char));
  if(!read_buffer){
    return;
  }
  memset(read_buffer, 0, block_size * sizeof(char));



  // Set Updated Modified Time
  t_modified = time(NULL);
  sprintf(t_modified_string, "%d", t_modified);

  start = fp_position;
  while (start % block_size){
    start--;
  }

  // Response Type
  strcpy(response_fields[0].field, "WRITE_RES");
  response_fields[0].length = strlen(response_fields[0].field);

  // Response Status
  strcpy(response_fields[1].field, "ACK");
  response_fields[1].length = strlen(response_fields[1].field);

  // Modified Time
  strcpy(response_fields[2].field, t_modified_string);
  response_fields[2].length = strlen(response_fields[2].field);


  // Insert or Update Block and Send to Client
  for(int i = 0; i < (int) ceil((double) bytes_to_write / block_size); i++){
    selected_block = get_block_from_file(file_container->files[file_index], start + block_size * i);
    if(!selected_block){
      empty_block_position = get_emtpy_block_position(file_container->files[file_index]);
      
      file_container->files[file_index]->blocks[empty_block_position] = (block_t *) malloc(sizeof(block_t));
      file_container->files[file_index]->blocks[empty_block_position]->start = start + block_size * i;
      file_container->files[file_index]->blocks[empty_block_position]->t_modified = t_modified;
      // printf("Not Exists\n");
    }
    else {
      selected_block->t_modified = t_modified;
      // printf("Exists\n");
    }

    // Read Modified Blocks
    lseek(file_container->files[file_index]->file_fd, start + block_size * i, SEEK_SET);
    bytes_read = read(file_container->files[file_index]->file_fd, read_buffer, block_size);
    
    // Set Data to Send
    memset(response_fields[3].field, 0, SIZE * sizeof(char));
    for(int j = 0; j < bytes_read; j++){
      response_fields[3].field[j] = read_buffer[j];
    }
    response_fields[3].length = bytes_read;

    // Length of Fields
    fields_length = 4;

    // Serialize Response from Fields
    serialized_response = serialize_request(response_fields, fields_length, &response_length);

    // Send Response
    sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
  }
  

}



void *udp_requests_handler(void *arguments){
  request_t *selected_request;
  char *request_type;
  

  while (1){
    // Select a Pending Request
    selected_request = pop_request(requests_list);
    
#ifdef DEBUG
    print_request(selected_request);
#endif

    request_type = selected_request->fields[0].field; 
    if(!strcmp(request_type, "LOOKUP_REQ")){
      lookup_handler(selected_request);
    }
    else if(!strcmp(request_type, "READ_REQ")){
      read_handler(selected_request);
    }
    else if(!strcmp(request_type, "WRITE_REQ")){
      write_handler(selected_request);
    }
    
      
    


    //   // Update Modified Time
    //   t_modified = time(NULL);
    //   for(int i = 0; )
    //   selected_block = get_block_from_file(file_container->files[file_position], start);
    //   if(!selected_block){
    //     empty_block_position = get_emtpy_block_position(file_container->files[file_position], start);
    //     file_container->files[file_position]->blocks[empty_block_position] = (block_t *) calloc(sizeof(block_t));
    //     file_container->files[file_position]->blocks[empty_block_position]->start = 
        
    //     file_container->files[file_position]->blocks[empty_block_position] = time(NULL);
    //   }

    //   // Allocate Memory for the Read Buffer based on Start/End positions
    //   read_buffer = (char *) calloc(end - start, sizeof(char));
    //   if(!read_buffer){
    //     continue;
    //   }

    //   // Read Data
    //   lseek(file_container->files[file_position]->file_fd, start, SEEK_SET);
    //   memset(read_buffer, 0, (end - start) * sizeof(char));
    //   bytes_read = read(file_container->files[file_position]->file_fd, read_buffer, (end - start) * sizeof(char));
      

    //   // Response Type
    //   strcpy(response_fields[0].field, "WRITE_RES");
    //   response_fields[0].length = strlen(response_fields[0].field);

    //   // T_MODIFIED
    //   sprintf(t_modified_string, "%d", file_container->files[file_position]->t_modified);
    //   strcpy(response_fields[1].field, t_modified_string);
    //   response_fields[1].length = strlen(response_fields[1].field);
      
    //   // Response Buffer
    //   // strncpy(response_fields[2].field, read_buffer, bytes_read);
    //   for(int i = 0; i < bytes_read; i++){
    //     response_fields[2].field[i] = read_buffer[i];
    //   }
    //   response_fields[2].length = bytes_read;

    //   // Total Fields
    //   fields_length = 3;
      
    //   // Serialize Response from Fields
    //   serialized_response = serialize_request(response_fields, fields_length, &response_length);
      
    //   // Send Response
    //   sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);


      


    // }
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
