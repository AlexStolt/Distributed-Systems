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
  int *current_flags, *requested_flags;

  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;

  file_path   = selected_request->fields[1].field;
  // Server will Ignore this Value
  flags       = atoi(selected_request->fields[2].field); 
 
  // Response Type
  strcpy(response_fields[0].field, "LOOKUP_RES");
  response_fields[0].length = strlen(response_fields[0].field);
      


  // Search if File is Already Open
  file_id = -1;
  for(int i = 0; i < file_container->length; i++){
    if(!file_container->files[i]){
      continue;
    }
    
    if(!strcmp(file_container->files[i]->file_path, file_path)){
      file_id = file_container->files[i]->file_id;
      
      // Close and Reopen File with Different Flags
      close(file_container->files[i]->file_fd);
      
      // Update Flags
      current_flags   = export_flags(file_container->files[i]->flags);
      requested_flags = export_flags(flags);
      if(!current_flags || !requested_flags){
        break;
      }

      file_container->files[i]->flags = 0;
      for(int j = 0; j < SUPPORTED_FlAGS; j++){
        if(current_flags[j] < 0){
          continue;
        }
        else if(current_flags[j] != O_CREAT && current_flags[j] != O_EXCL && current_flags[j] != O_CREAT){
          file_container->files[i]->flags = file_container->files[i]->flags | current_flags[j];
        }
      }

      file_container->files[i]->file_fd = open(file_path, file_container->files[i]->flags); 
      if(file_container->files[i]->file_fd < 0){
        // Response Status
        strcpy(response_fields[1].field, "NACK");
        response_fields[1].length = strlen(response_fields[1].field);
        
        // Total Fields
        fields_length = 2;

        // Serialize Response from Fields
        serialized_response = serialize_request(response_fields, fields_length, &response_length);
        
        // Send Response
        sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
        return;
      }
      
      break;
    }
  }

  // Try to Open File
  if(file_id < 0){
    fd = open(file_path, flags, S_IRWXU);
    printf("fd: %d\n", fd);
    if(fd >= 0){
      file = (file_t *) malloc(sizeof(file_t));
      if(!file){
        exit(EXIT_FAILURE);
      }

      file_id = file_container->current_id;

      strcpy(file->file_path, file_path);
      file->file_id = file_container->current_id;
      file->file_fd = fd;
      file->flags = flags;
      for(int i = 0; i < SIZE; i++){
        file->blocks[i] = NULL;
      }


      file_container->files[file_container->length] = file;
      file_container->length++;
      file_container->current_id++;
    }
  }

  
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

    // Reincarnation Number
    memset(response_fields[4].field, 0, SIZE * sizeof(char));
    sprintf(response_fields[4].field, "%d", current_reincarnation_number);
    response_fields[4].length = strlen(response_fields[4].field);

    // Total Fields
    fields_length = 5;
  }

  // Serialize Response from Fields
  serialized_response = serialize_request(response_fields, fields_length, &response_length);
  
  // Send Response
  sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
}


void read_handler(request_t *selected_request){
  int file_id, reincarnation_number, block_start, block_size, t_modified;
  int file_index;
  char *read_buffer;
  ssize_t bytes_read;
  block_t *selected_block;
  bool block_modified;
  int block_modified_time;
  char t_modified_string[SIZE];
  int start;
  int end;

  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;

  // Get Request Fields
  file_id               = atoi(selected_request->fields[1].field);
  reincarnation_number  = atoi(selected_request->fields[2].field);
  block_start           = atoi(selected_request->fields[3].field);
  block_size            = atoi(selected_request->fields[4].field);
  t_modified            = atoi(selected_request->fields[5].field);

  printf("%d %d %d %d %d\n", file_id, reincarnation_number, block_start, block_size, t_modified);
  fflush(stdout);
  
  // Response Type
  strcpy(response_fields[0].field, "READ_RES");
  response_fields[0].length = strlen(response_fields[0].field);

  if(reincarnation_number != current_reincarnation_number){
    strcpy(response_fields[1].field, "NACK");
    response_fields[1].length = strlen(response_fields[1].field);

    strcpy(response_fields[2].field, "INVALID REINCARNATION NUMBER");
    response_fields[2].length = strlen(response_fields[2].field);

    // Total Fields
    fields_length = 3;
  }
  else {
    // Search for File FD using its ID
    file_index = get_fd_by_id(file_container, file_id);
    if(file_index < 0){
      strcpy(response_fields[1].field, "NACK");
      response_fields[1].length = strlen(response_fields[1].field);

      strcpy(response_fields[2].field, "FILE NOT FOUND");
      response_fields[2].length = strlen(response_fields[2].field);

      // Total Fields
      fields_length = 3;
    }
    else {
      // Allocate Memory for the Read Buffer based on the Length
      read_buffer = (char *) calloc(block_size, sizeof(char));
      if(!read_buffer){
        strcpy(response_fields[1].field, "NACK");
        response_fields[1].length = strlen(response_fields[1].field);

        strcpy(response_fields[2].field, "FATAL MALLOC ERROR");
        response_fields[2].length = strlen(response_fields[2].field);

        // Total Fields
        fields_length = 3;
      }
      else {
        memset(read_buffer, 0, block_size * sizeof(char));
        start = block_start;
        end = start + block_size;

        // Find Block (Overlap) and check if block was modified
        // selected_block = get_block_from_file(file_container->files[file_index], block_start);
        selected_block = NULL;
        block_modified = false;
        block_modified_time = -1;
        for(int j = 0; j < SIZE; j++){
          if(!file_container->files[file_index]->blocks[j]){
            continue;
          }
          // Current Start of Block is Larger than the End of Checking Block
          if(start > file_container->files[file_index]->blocks[j]->end){
            continue;
          }
          // Current End of Block is Smaller than the Start of Checking Block
          else if(end < file_container->files[file_index]->blocks[j]->start){
            continue;
          }

          // Blocks Overlaps and Maximum Modified Time is Selected
          if (t_modified < file_container->files[file_index]->blocks[j]->t_modified){
            block_modified = true;
            if (block_modified_time < file_container->files[file_index]->blocks[j]->t_modified){
              block_modified_time = file_container->files[file_index]->blocks[j]->t_modified;
              selected_block = file_container->files[file_index]->blocks[j];
            }
          }
        }


        if((!selected_block && t_modified < 0) || block_modified){
          lseek(file_container->files[file_index]->file_fd, block_start, SEEK_SET);
          bytes_read = read(file_container->files[file_index]->file_fd, read_buffer, block_size);
          
          // Read Status
          if(bytes_read < 0){
            strcpy(response_fields[1].field, "NACK");
            response_fields[1].length = strlen(response_fields[1].field);

            strcpy(response_fields[2].field, "NO BYTES READ");
            response_fields[2].length = strlen(response_fields[2].field);

            // Total Fields
            fields_length = 3;
          }
          else {
            strcpy(response_fields[1].field, "ACK");
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
            for(int i = 0; i < bytes_read; i++){
              response_fields[3].field[i] = read_buffer[i];
            }
            response_fields[3].length = bytes_read;

            // Total Fields
            fields_length = 4;

            // Free the Read Buffer Memory
            free(read_buffer);
          }
        }
        else if(!block_modified){
          strcpy(response_fields[1].field, "ACK");
          response_fields[1].length = strlen(response_fields[1].field);

          fields_length = 2;
        }
      }
    }
  }
  
  
  // Serialize Response from Fields
  serialized_response = serialize_request(response_fields, fields_length, &response_length);
  
  // Send Response
  sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
}


void write_handler(request_t *selected_request){
  int file_id, reincarnation_number, fp_position, bytes_to_write, block_size;
  char *buffer_to_write;
  char *read_buffer;
  int file_index;
  int bytes_written;
  int bytes_read;
  int t_modified; 
  block_t *selected_block;
  int start;
  int end;
  int bof;
  int eof;
  int empty_block_position;
  char t_modified_string[SIZE];
  char *eof_flag;
  int current_position;


  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;


  // Request Fields
  file_id               = atoi(selected_request->fields[1].field);
  reincarnation_number  = atoi(selected_request->fields[2].field);
  eof_flag              = selected_request->fields[3].field;
  fp_position           = atoi(selected_request->fields[4].field);
  bytes_to_write        = atoi(selected_request->fields[5].field);
  buffer_to_write       = selected_request->fields[6].field;
  block_size            = atoi(selected_request->fields[7].field);
  
  

  bof = -1;
  eof = -1;
  current_position = 0;


  if(reincarnation_number != current_reincarnation_number){
    strcpy(response_fields[1].field, "NACK");
    response_fields[1].length = strlen(response_fields[1].field);

    strcpy(response_fields[2].field, "INVALID REINCARNATION NUMBER");
    response_fields[2].length = strlen(response_fields[2].field);

    // Total Fields
    fields_length = 3;
  } 
  else {
    file_index = get_fd_by_id(file_container, file_id);
    if(file_index < 0){
      strcpy(response_fields[1].field, "NACK");
      response_fields[1].length = strlen(response_fields[1].field);

      strcpy(response_fields[2].field, "FILE NOT FOUND");
      response_fields[2].length = strlen(response_fields[2].field);

      // Total Fields
      fields_length = 3;
    }
    else {
      // SEEK_END
      if(!strcmp("eof", eof_flag)){
        bof = lseek(file_container->files[file_index]->file_fd, (size_t) 0, SEEK_SET);
        eof = lseek(file_container->files[file_index]->file_fd, (size_t) 0, SEEK_END);
        fp_position += (eof - bof);        
      }
      
      lseek(file_container->files[file_index]->file_fd, fp_position, SEEK_SET);
      bytes_written = write(file_container->files[file_index]->file_fd, buffer_to_write, bytes_to_write);
      if(bytes_written < 0){
        strcpy(response_fields[1].field, "NACK");
        response_fields[1].length = strlen(response_fields[1].field);

        strcpy(response_fields[2].field, "NO BYTES WRITTEN");
        response_fields[2].length = strlen(response_fields[2].field);

        // Total Fields
        fields_length = 3;
      }
      else {
        // Allocate Memory for the Read Buffer based on the Length
        read_buffer = (char *) calloc(block_size, sizeof(char));
        if(!read_buffer){
          strcpy(response_fields[1].field, "NACK");
          response_fields[1].length = strlen(response_fields[1].field);

          strcpy(response_fields[2].field, "NO BYTES READ");
          response_fields[2].length = strlen(response_fields[2].field);

          // Total Fields
          fields_length = 3;
        }
        else {
          // Set Updated Modified Time
          t_modified = time(NULL);
          sprintf(t_modified_string, "%d", t_modified);

          if(!strcmp("eof", eof_flag)){
            start = eof;
          }
          else {
            start = fp_position;
          }
          while (start % block_size){
            start--;
          }

          end = fp_position + bytes_to_write;
          while (end % block_size){
            end++;
          }
          printf("%d %d\n", start, end);
          // Update Overlaping Blocks
          for(int j = 0; j < SIZE; j++){
            if(!file_container->files[file_index]->blocks[j]){
              continue;
            }
            // Current Start of Block is Larger than the End of Checking Block
            if(start > file_container->files[file_index]->blocks[j]->end){
              continue;
            }
            // Current End of Block is Smaller than the Start of Checking Block
            else if(end < file_container->files[file_index]->blocks[j]->start){
              continue;
            }

            // Blocks Overlap
            file_container->files[file_index]->blocks[j]->t_modified = t_modified;
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

          // Amount of Bytes Written
          sprintf(response_fields[3].field, "%d", bytes_written);
          response_fields[3].length = strlen(response_fields[3].field);


          /* [IMPORTANT NOTE]
            Multiple overlapping blocks may be inserted. This is not and error since these blocks
            are checked only when read operations are performed. When reading all overlapping blocks are
            checked. If at least one (overlaping) modified block is found then the block was for sure modified.
            If multiple blocks are found th modified time is the maximum between all the blocks modified.
            Not the most elegant solution but works for dynamic block size specified by the client side.  
          */
         
          // Insert or Update Block and Send to Client
          for(int i = 0; i < (int) ceil((double) (end - start) / block_size); i++){
            selected_block = get_block_from_file(file_container->files[file_index], start + block_size * i);
            if(!selected_block){
              empty_block_position = get_emtpy_block_position(file_container->files[file_index]);
              
              file_container->files[file_index]->blocks[empty_block_position] = (block_t *) malloc(sizeof(block_t));
              file_container->files[file_index]->blocks[empty_block_position]->start = start + block_size * i;
              file_container->files[file_index]->blocks[empty_block_position]->end = file_container->files[file_index]->blocks[empty_block_position]->start + block_size;
              file_container->files[file_index]->blocks[empty_block_position]->t_modified = t_modified;
            }
            else {
              selected_block->t_modified = t_modified;
            }

            // Read Modified Blocks
            memset(read_buffer, 0, block_size * sizeof(char));
            lseek(file_container->files[file_index]->file_fd, start + block_size * i, SEEK_SET);
            bytes_read = read(file_container->files[file_index]->file_fd, read_buffer, block_size);
            
            // Set Data to Send
            memset(response_fields[4].field, 0, SIZE * sizeof(char));
            for(int j = 0; j < bytes_read; j++){
              response_fields[4].field[j] = read_buffer[j];
            }
            response_fields[4].length = bytes_read;

            // EOF for SEEK_END
            sprintf(response_fields[5].field, "%d", eof);
            response_fields[5].length = strlen(response_fields[5].field);

            current_position = lseek(file_container->files[file_index]->file_fd, 0, SEEK_CUR);
            printf("%d\n", current_position);

            // Current Offset in File
            sprintf(response_fields[6].field, "%d", current_position);
            response_fields[6].length = strlen(response_fields[6].field);

            // Length of Fields
            fields_length = 7;

            // Serialize Response from Fields
            serialized_response = serialize_request(response_fields, fields_length, &response_length);

            // Send Response
            sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
          }
        }
      }
    } 
  }
}


void truncate_handler(request_t *selected_request){
  int file_id, reincarnation_number, length;
  int truncate_status;
  int file_index;
  int t_modified;

  // Response
  char *serialized_response;
  field_t response_fields[SIZE];
  int response_length;
  int fields_length;


  file_id               = atoi(selected_request->fields[1].field);
  reincarnation_number  = atoi(selected_request->fields[2].field);
  length                = atoi(selected_request->fields[3].field);


  // Response Type
  strcpy(response_fields[0].field, "TRUNCATE_RES");
  response_fields[0].length = strlen(response_fields[0].field);

  // Check Reincarnation
  if(reincarnation_number != current_reincarnation_number){
    strcpy(response_fields[1].field, "NACK");
    response_fields[1].length = strlen(response_fields[1].field);

    strcpy(response_fields[2].field, "INVALID REINCARNATION NUMBER");
    response_fields[2].length = strlen(response_fields[2].field);

    // Total Fields
    fields_length = 3;
  }
  else {
    // Find FD from ID
    file_index = get_fd_by_id(file_container, file_id);
    if(file_index < 0){
      strcpy(response_fields[1].field, "NACK");
      response_fields[1].length = strlen(response_fields[1].field);

      strcpy(response_fields[2].field, "FILE NOT FOUND");
      response_fields[2].length = strlen(response_fields[2].field);

      // Total Fields
      fields_length = 3;
    }
    else {
      // Truncate File
      truncate_status = ftruncate(file_container->files[file_index]->file_fd, length);
      if(truncate_status < 0){
        strcpy(response_fields[1].field, "NACK");
        response_fields[1].length = strlen(response_fields[1].field);

        strcpy(response_fields[2].field, "TRUNCATE RETURN -1");
        response_fields[2].length = strlen(response_fields[2].field);

        // Total Fields
        fields_length = 3;
      }
      else {
        strcpy(response_fields[1].field, "ACK");
        response_fields[1].length = strlen(response_fields[1].field);

        // Set Updated Modified Time
        t_modified = time(NULL);
        sprintf(response_fields[2].field, "%d", t_modified);
        response_fields[2].length = strlen(response_fields[2].field);

        // Total Fields
        fields_length = 3;
        
        // Update Modified Blocks
        for(int i = 0; i < SIZE; i++){
          if(!file_container->files[file_index]->blocks[i]){
            continue;
          }
          // Current Length of File is Larger than the End of Checking Block
          if(length >= file_container->files[file_index]->blocks[i]->end){
            printf("Skip %d %d\n", file_container->files[file_index]->blocks[i]->start, file_container->files[file_index]->blocks[i]->end);
            continue;
          }
          file_container->files[file_index]->blocks[i]->t_modified = t_modified;
          printf("Truncate %d %d\n", file_container->files[file_index]->blocks[i]->start, file_container->files[file_index]->blocks[i]->end);
        }
      }
    }
  }

  // Serialize Response from Fields
  serialized_response = serialize_request(response_fields, fields_length, &response_length);
  
  // Send Response
  sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
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
    else if(!strcmp(request_type, "TRUNCATE_REQ")){
      truncate_handler(selected_request);
    }
  }
}


void nfs_server_init(){
  pthread_t udp_requests_listener_daemon;
  pthread_t udp_requests_handler_daemon;
  char reincarnation_str[SIZE];
  int reincarnation_number;
  
  requests_list = requests_list_init();
  unicast_socket_fd = _unicast_socket_init();
  file_container = files_init();

  // Read Previous Reincarnation Number
  reincarnation_file_fp = fopen("reincarnation.config", "r");
  if(!reincarnation_file_fp){
    reincarnation_number = 0;
  }
  else {
    memset(reincarnation_str, 0, SIZE * sizeof(char));
    fgets(reincarnation_str, SIZE, reincarnation_file_fp);
    if(strlen(reincarnation_str) > 0)
      reincarnation_number = atoi(reincarnation_str);
    else 
      reincarnation_number = 0;

    fclose(reincarnation_file_fp);
  }

  reincarnation_number = reincarnation_number + 1;

  // Write Current Reincarnation Number
  reincarnation_file_fp = fopen("reincarnation.config", "w+");
  memset(reincarnation_str, 0, SIZE * sizeof(char));
  sprintf(reincarnation_str, "%d", reincarnation_number);
  fwrite(reincarnation_str, sizeof(char), strlen(reincarnation_str), reincarnation_file_fp);
  fclose(reincarnation_file_fp);

  // Set the Current Reincarnation Number
  current_reincarnation_number = reincarnation_number;

  if(pthread_create(&udp_requests_listener_daemon, NULL, udp_requests_listener, NULL) != 0){
    exit(EXIT_FAILURE);
  }

  if(pthread_create(&udp_requests_handler_daemon, NULL, udp_requests_handler, NULL) != 0){
    exit(EXIT_FAILURE);
  }


  pthread_join(udp_requests_listener_daemon, NULL);
  pthread_join(udp_requests_handler_daemon, NULL);
}
