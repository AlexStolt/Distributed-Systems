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
  char response_fields[SIZE][SIZE];
  int fields_length;
  char *serialized_response;
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
        strcpy(response_fields[0], "LOOKUP_RES");
        strcpy(response_fields[1], "NACK");
        fields_length = 2;
      }
      else {
        strcpy(response_fields[0], "LOOKUP_RES");
        strcpy(response_fields[1], "ACK");
        strcpy(response_fields[2], file_path);
        
        sprintf(file_id_string, "%d", file_id);
        strcpy(response_fields[3], file_id_string);
        fields_length = 4;
      }

      // Serialize Response from Fields
      serialized_response = serialize_request(response_fields, fields_length, &response_length);
      
      // Send Response
      sendto(unicast_socket_fd, serialized_response, response_length * sizeof(char), 0, &selected_request->source, selected_request->address_length);
    }
    else if(!strcmp(request_type, "READ_REQ")){

    }

  }
}



int _unicast_socket_init(){
  int unicast_fd;
  struct sockaddr_in server_addr;
  int enable = 1;

  if((unicast_fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0){
    exit(EXIT_FAILURE);
  }
      
  memset(&server_addr, 0, sizeof(server_addr));
  server_addr.sin_family = AF_INET;
  server_addr.sin_addr.s_addr = INADDR_ANY;
  server_addr.sin_port = htons(PORT);
  
  if (setsockopt(unicast_fd, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(int)) < 0){
    exit(EXIT_FAILURE);
  }

  if(bind(unicast_fd, (const struct sockaddr *) &server_addr, sizeof(server_addr)) < 0){  
    exit(EXIT_FAILURE);
  }
  
  return unicast_fd;
}


file_container_t *files_init(){
  file_container_t *file_container;

  file_container = (file_container_t *) calloc(SIZE, sizeof(file_t));
  if(!file_container){
    exit(EXIT_FAILURE);
  }

  return file_container;
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
