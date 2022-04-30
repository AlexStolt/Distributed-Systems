#include "nfs.h"


requests_list_t *requests_list_init(){
  requests_list_t *requests_list;

  requests_list = (requests_list_t *) malloc(sizeof(requests_list_t));
  if(!requests_list){
    exit(EXIT_FAILURE);
  }
  
  requests_list->head = NULL;
  requests_list->tail = NULL;
  requests_list->length = 0;

  if(pthread_mutex_init(&requests_list->list_mutex, NULL) != 0){
    exit(EXIT_FAILURE);
  }

  if(sem_init(&requests_list->block_semaphore, 0, 0) != 0){
    exit(EXIT_FAILURE);
  }

  return requests_list;
}


void append_request(requests_list_t *requests_list, request_t *request){
  pthread_mutex_lock(&requests_list->list_mutex);
  
  if(!requests_list->head || !requests_list->tail){
    requests_list->head = request;
    requests_list->tail = request;
  }

  requests_list->tail->next = request;
  request->next = requests_list->head;
  requests_list->tail = request;
  requests_list->length++;

  sem_post(&requests_list->block_semaphore);
  pthread_mutex_unlock(&requests_list->list_mutex);
}


request_t *pop_request(requests_list_t *requests_list){
  request_t *popped_request;

  sem_wait(&requests_list->block_semaphore);
  pthread_mutex_lock(&requests_list->list_mutex);

  popped_request = requests_list->head;
  if(requests_list->length < 2){
    requests_list->head = NULL;
    requests_list->tail = NULL;
  }
  else {
    requests_list->head = requests_list->head->next;
    requests_list->tail->next = requests_list->head;
  }
  
  requests_list->length--;

  pthread_mutex_unlock(&requests_list->list_mutex);

  return popped_request;
}


void print_requests(requests_list_t *requests_list){
  request_t *current;

  for(current = requests_list->head; current != requests_list->tail; current = current->next){
    printf("%d:%s", current->data_length, current->data);
  }

  printf("%d:%s", current->data_length, current->data);
}


void print_address(struct sockaddr *address){
  struct sockaddr_in *address_in;
  char ip[INET_ADDRSTRLEN];

  address_in = (struct sockaddr_in *) address;
  inet_ntop(AF_INET, &(address_in->sin_addr), ip, INET_ADDRSTRLEN);
  printf("%s:%d\n", ip, ntohs(address_in->sin_port));
}


void *udp_requests_listener(void *arguments){
  request_t *request;

  while (1) {
    request = (request_t *) malloc(sizeof(request_t));
    if(!request){
      exit(EXIT_FAILURE);
    }

    memset(request->data, 0, SIZE * sizeof(char));
    memset(&request->source, 0, sizeof(struct sockaddr));
    memset(&request->address_length, 0, sizeof(socklen_t));

    request->address_length = sizeof(struct sockaddr);
    request->data_length = recvfrom(unicast_socket_fd, request->data, SIZE * sizeof(char), 0, &request->source, &request->address_length);
    if(request->data_length < 0){
      continue;
    }

    // print_address(&request->source);

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
  char response[SIZE];


  while (1){
    
    selected_request = pop_request(requests_list);
    memset(response, 0, SIZE * sizeof(char));

    // printf("%s", selected_request->data);
    // fflush(stdout);

    request_type = strtok(selected_request->data, ":");
    
    if(!strcmp(request_type, "LOOKUP_REQ")){
      flags = atoi(strtok(NULL, ":"));
      file_path = strtok(NULL, "");
 
      file_id = lookup_handler(file_path, flags);
      if(file_id < 0){
       strcpy(response, "LOOKUP_RES:NACK"); 
      }
      else {
        sprintf(response, "LOOKUP_RES%sACK%s%s%s%d", SEPERATOR, SEPERATOR, file_path, SEPERATOR, file_id);
      }
      
      // Send Response
      sendto(unicast_socket_fd, response, strlen(response) * sizeof(char), 0, &selected_request->source, selected_request->address_length);
      printf("Sending %s %ld\n", response, strlen(response));
    
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
