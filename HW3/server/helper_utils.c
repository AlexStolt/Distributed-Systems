#include "nfs.h"

void print_address(struct sockaddr *address){
  struct sockaddr_in *address_in;
  char ip[INET_ADDRSTRLEN];

  address_in = (struct sockaddr_in *) address;
  inet_ntop(AF_INET, &(address_in->sin_addr), ip, INET_ADDRSTRLEN);
  printf("%s:%d\n", ip, ntohs(address_in->sin_port));
}


int get_next_integer(char *string, char **end_pointer){
  char *pointer = string;
  long integer;
  while (*pointer) {
    if(isdigit(*pointer)) {
      integer = strtol(pointer, &pointer, 10);
      *end_pointer = pointer + 1;
      return integer;

    } else {
      pointer++;
    }
  }
  return -1;
}

char *serialize_request(char fields[SIZE][SIZE], int fields_length, int *serialized_request_length){
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
    field_length = strlen(fields[i]);
    sprintf(field_length_string, "%d", field_length);
    strncpy(local_serialized_request + offset, field_length_string, strlen(field_length_string));
    offset = offset + strlen(field_length_string) + 1;
     
    // Append Field
    strncpy(local_serialized_request + offset, fields[i], strlen(fields[i]));
    offset = offset + strlen(fields[i]);
    //break;
  }

  
  sprintf(offset_str, "%d", offset);
  strcpy(serialized_request, offset_str);
  for(int i = 0; i < offset; i++){
    serialized_request[strlen(offset_str) + i + 1] = local_serialized_request[i];
  }

  *serialized_request_length = offset + strlen(offset_str) + 1;

  return serialized_request;
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