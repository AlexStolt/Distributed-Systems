#include "nfs.h"

void print_address(struct sockaddr *address){
  struct sockaddr_in *address_in;
  char ip[INET_ADDRSTRLEN];

  address_in = (struct sockaddr_in *) address;
  inet_ntop(AF_INET, &(address_in->sin_addr), ip, INET_ADDRSTRLEN);
  printf("%s:%d\n", ip, ntohs(address_in->sin_port));
}


char *serialize_request(field_t *fields, int fields_length, int *serialized_request_length){
  char *serialized_request;
  char local_serialized_request[SIZE]; 
  int field_length = 0;
  char field_length_string[SIZE];
  int offset = 0;
  char offset_str[SIZE];
  
  // Allocate Memory for the Request
  serialized_request = (char *) calloc(SIZE, sizeof(char));
  if(!serialized_request){
    return NULL;
  }

  for(int i = 0; i < fields_length; i++){
    // Calculate the Field Length and Append
    field_length = fields[i].length;
    sprintf(field_length_string, "%d", field_length);
    strncpy(local_serialized_request + offset, field_length_string, strlen(field_length_string));
    
    // Add a NULL Separator to String
    offset = offset + strlen(field_length_string);
    local_serialized_request[offset] = '\0';
    
    // Go a Byte Next to the NULL Separator
    offset =  offset + 1;

    // Append Field
    for(int j = 0; j < fields[i].length; j++){
      local_serialized_request[offset + j] = fields[i].field[j];
    }
    offset = offset + fields[i].length;
  }

  
  sprintf(offset_str, "%d", offset);
  strcpy(serialized_request, offset_str);
  for(int i = 0; i < offset; i++){
    serialized_request[strlen(offset_str) + i + 1] = local_serialized_request[i];
  }

  *serialized_request_length = offset + strlen(offset_str) + 1;

  return serialized_request;
}


block_t *get_block_from_file(file_t *file, int start){
  int i;

  i = 0;
  while(file->blocks[i]){
    if(file->blocks[i]->start != start){
      i++;
      continue;
    }
    return file->blocks[i];
  }
  return NULL;
}


int get_emtpy_block_position(file_t *file){
  int i;

  i = 0;
  while(file->blocks[i]){
    i++;
  }
  return i;
}


field_t *parse_request(char *request, int *fields_length){
  field_t *fields;
  int length = -1;
  int request_length;
  int offset = 0;
  int request_start = 0;

  fields = (field_t *) calloc(SIZE, sizeof(field_t));
  if(!fields){
    return NULL;
  }
  
  request_length = atoi(request);
  do {
    request_start++;
  } while (request[request_start]);

  offset = request_start + 1;
  while (offset < request_length + request_start){
    length = atoi(request + offset);
    do {
      offset++;
    } while (request[offset]);

    for(int i = 0; i < length; i++){
      fields[*fields_length].field[i] = request[offset + i + 1];
    }
    fields[*fields_length].length = length;

    *fields_length = *fields_length + 1;
    offset = offset + length + 1;
  }
  
  return fields;
}


void print_request(request_t *request){
  for(int i = 0; i < request->fields_length; i++){
    printf("%s ", request->fields[i].field);
  }
  printf("\n");
  fflush(stdout);
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


int get_fd_by_id(file_container_t *file_container, int file_id){
  int file_position;
  
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

  return file_position;
}




// ******************************************************** List Utilities ********************************************************//
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