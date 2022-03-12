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

#define GROUP_IP "224.1.1.1"
#define GROUP_PORT 8000
#define MESSAGE_LENGTH 1024
#define PFDS_SIZE 1
#define TIMEOUT 1000
#define TRIES 4
#define MULTICAST_WINDOW 5

void api_init();
int RequestReply (int svcid, void *reqbuf, int reqlen, void *rspbuf, int *rsplen);