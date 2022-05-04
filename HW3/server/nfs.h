#ifndef NFS_HEADER
#define NFS_HEADER

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <time.h>
#include <limits.h>
#include <poll.h>
#include <fcntl.h>
#include <stdbool.h>
#include <pthread.h>
#include <semaphore.h>
#include <ctype.h>

#define PORT 8080
#define SIZE 1024
#define SEPERATOR "|"

#define DEBUG


typedef struct field {
  int length;
  char field[SIZE];
} field_t;

typedef struct request {
  struct sockaddr source;
  socklen_t address_length;
  field_t *fields;
  int fields_length;
  struct request *next;
} request_t;


typedef struct requests_list {
  struct request *head;
  struct request *tail;
  int length;
  pthread_mutex_t list_mutex;
  sem_t block_semaphore;
} requests_list_t;






typedef struct file {
  char file_path[SIZE];
  int file_id;
  int file_fd;
  int t_modified;
} file_t;


typedef struct file_container {
  int length;
  int current_id;
  file_t *files[SIZE];
} file_container_t;


int unicast_socket_fd;
requests_list_t *requests_list;
file_container_t *file_container;


field_t *parse_request(char *request, int *fields_length);
void print_request(request_t *request);
char *serialize_request(field_t *fields, int fields_length, int *serialized_request_length);
requests_list_t *requests_list_init();
void append_request(requests_list_t *requests_list, request_t *request);
request_t *pop_request(requests_list_t *requests_list);
file_container_t *files_init();
int _unicast_socket_init();

void nfs_server_init();



#endif