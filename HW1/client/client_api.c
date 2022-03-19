#include "client_api.h"

typedef struct {
  nfds_t nfds;
  nfds_t pfds_size;
  struct pollfd *pfds;
} poll_information_t;

typedef struct {
    struct sockaddr_in unicast_ping_server_address;
    int service_id;
} ping_arguments_t;

struct in_addr local_interface;
struct sockaddr_in group_address;
int multicast_socket_fd;
int unicast_socket_fd;
int ping_server_socket_fd;
char databuf[MESSAGE_LENGTH] = "Multicast test message lol!";
int datalen = sizeof(databuf);
int sequence = 0;
poll_information_t multicast_poll_information, unicast_poll_information, keepalive_poll_information;
bool ABORT_FLAG = false;
bool JOIN_THREAD = false;

// Poll related information
void pfds_init(poll_information_t *poll_information, nfds_t size){
  poll_information->pfds_size = size;
  poll_information->pfds = (struct pollfd *) malloc(poll_information->pfds_size * sizeof(struct pollfd));
  if(!poll_information){
      exit(EXIT_FAILURE);
  }
}

void disable_blocking(int socket_fd){
  int flags = fcntl(socket_fd, F_GETFL);

  // Set to Non-Blocking Socket
  flags |= O_NONBLOCK;
  fcntl(socket_fd, F_SETFL, flags);
}

void pfds_add(poll_information_t *poll_information, int socket_fd){
  if(poll_information->nfds >= poll_information->pfds_size){
    exit(EXIT_FAILURE);
  }

  // Add socket to poll
  poll_information->pfds[poll_information->nfds].fd = socket_fd;
  poll_information->pfds[poll_information->nfds].events = POLLIN;
  
  // Increment count of sockets in poll
  poll_information->nfds++;
}


bool check_polling(poll_information_t *poll_information, int socket_fd, int timeout){
  int events = poll(poll_information->pfds, poll_information->nfds, timeout);
  int polling;

  if(!events){
    return false;
  }

  for(nfds_t i = 0; i < poll_information->nfds; i++){
    if(poll_information->pfds[i].fd != socket_fd){
      continue;
    }
    polling = poll_information->pfds[i].revents & POLLIN;
    if(!polling){
      return false;
    }
    else {
      return true;
    }
  }  

  return false;
}


void api_init() {
    //Create multicast socket
    multicast_socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (multicast_socket_fd < 0) {
        perror("Opening datagram socket error");
        exit(EXIT_FAILURE);
    }

    //Multicast address
    memset((char *) &group_address, 0, sizeof(group_address));
    group_address.sin_family = AF_INET;
    group_address.sin_addr.s_addr = inet_addr(GROUP_IP);
    group_address.sin_port = htons(GROUP_PORT);

    //Address of the client
    local_interface.s_addr = INADDR_ANY;

    //Multicast socket
    if (setsockopt(multicast_socket_fd, IPPROTO_IP, IP_MULTICAST_IF, (char *) &local_interface, sizeof(local_interface)) < 0) {
        perror("Setting local interface error");
        exit(EXIT_FAILURE);
    }

    // Enable Polling in Multicast Socket
    pfds_init(&multicast_poll_information, PFDS_SIZE);
    disable_blocking(multicast_socket_fd);
    pfds_add(&multicast_poll_information, multicast_socket_fd);


    // Creating unicast socket
    if ((unicast_socket_fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("socket creation failed");
        exit(EXIT_FAILURE);
    }

     // Enable Polling in Unicast Socket
    pfds_init(&unicast_poll_information, PFDS_SIZE);
    disable_blocking(unicast_socket_fd);
    pfds_add(&unicast_poll_information, unicast_socket_fd);


    // Create Keepalive Socket
    if ((ping_server_socket_fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("socket creation failed");
        exit(EXIT_FAILURE);
    }

    // Enable Polling in Keepalive Socket
    pfds_init(&keepalive_poll_information, PFDS_SIZE);
    disable_blocking(ping_server_socket_fd);
    pfds_add(&keepalive_poll_information, ping_server_socket_fd);
}

int multicast_discovery(int service_id, struct sockaddr_in *unicast_server_address){
    socklen_t length = sizeof(struct sockaddr_in);
    char multicast_response[MESSAGE_LENGTH];
    char multicast_request[MESSAGE_LENGTH];
    const char delimiter[2] = ":";
    int server_load = INT_MAX;
    char *token;
    time_t waiting_multicast_responses_time;
    bool retry = true;

    //Initialize buffers
    memset(multicast_response, 0, MESSAGE_LENGTH * sizeof(char));
    memset(multicast_request, 0, MESSAGE_LENGTH * sizeof(char));
    waiting_multicast_responses_time = time(NULL) + MULTICAST_WINDOW;
    //unicast_server_address->sin_family = AF_INET;
    
    // Request Header and Payload
    sprintf(multicast_request, "%d", service_id);

    //Send multicast socket
    for(int i = 0; i < TRIES; i++){
        sendto(multicast_socket_fd, multicast_request, 3, MSG_CONFIRM, (const struct sockaddr *) &group_address, sizeof(group_address));

        while(time(NULL) < waiting_multicast_responses_time){
            memset(multicast_response, 0, MESSAGE_LENGTH);
            if(!check_polling(&multicast_poll_information, multicast_socket_fd, TIMEOUT)){
                break;
            }
            //Receive from servers multicast connection
            if (recvfrom(multicast_socket_fd, (void *) multicast_response, MESSAGE_LENGTH, MSG_WAITALL, (struct sockaddr *) unicast_server_address, &length) < 0) {
                perror("recvfrom failed");
                exit(EXIT_FAILURE);
            }
            
            // Messages were received by at least by one server 
            retry = false;

            //Decoding server's message and keeps the best one
            token = strtok(multicast_response, delimiter);

            if(strcmp(token, "ACK") != 0) {
                continue;
            }

            // Found Service 
            token = strtok(NULL, delimiter);
            if(atoi(token) < server_load) {
                server_load = atoi(token);
            }
        }

        if(server_load < INT_MAX){
            // Success
            return 0;
        }
        
        if(!retry){
            //At Least One Request Reached Servers
            return -1; 
        }
    }

    // Server was found
    if(server_load < INT_MAX){
        // Success
        return 0;
    }

    // No Servers were found
    return -2;
}

void *ping_server(void *arguments){
    char ping_server_request[MESSAGE_LENGTH];
    char ping_server_response[MESSAGE_LENGTH];
    ping_arguments_t ping_arguments = *((ping_arguments_t *) arguments);
    struct sockaddr_in ping_server_address = (struct sockaddr_in) ping_arguments.unicast_ping_server_address;
    socklen_t length = sizeof(ping_server_address);
    int service_id = ping_arguments.service_id;


    memset(ping_server_request, 0, MESSAGE_LENGTH * sizeof(char));
    sprintf(ping_server_request, "PING:%d", service_id);

    for(int i = 0; i < TRIES; i++){
        if(JOIN_THREAD){
            return NULL;
        }
       
        memset(ping_server_response, 0, MESSAGE_LENGTH * sizeof(char));

        sendto(ping_server_socket_fd, ping_server_request, strlen(ping_server_request) * sizeof(char), 0, (struct sockaddr *) &ping_server_address, length);
        if(!check_polling(&keepalive_poll_information, ping_server_socket_fd, TIMEOUT)){
            continue;
        }

        if (recvfrom(ping_server_socket_fd, (void *) ping_server_response, MESSAGE_LENGTH, MSG_WAITALL, (struct sockaddr *) &ping_server_address, &length) < 0) {
            perror("recvfrom ack failed");
            exit(EXIT_FAILURE);
        }

        if(!strcmp(ping_server_response, "ACK")) {
            i = 0;
        }
    }

    // Client should stop trying
    ABORT_FLAG = true;

    return NULL;
}

int unicast_communication(int service_id, void *request_buffer, int request_length, void *response_buffer, int *response_length, struct sockaddr_in unicast_server_address){
    char unicast_ping_response[MESSAGE_LENGTH];
    void *unicast_request;
    char unicast_ack[MESSAGE_LENGTH];
    char acknowledgement[MESSAGE_LENGTH] = "ACK";
    struct sockaddr_in unicast_ping_server_address;
    socklen_t length = sizeof(unicast_ping_server_address);
    pthread_t ping_server_thread;
    ping_arguments_t ping_arguments;
    char seperator[] = ":";
    int service_id_to_network = htonl(service_id);
    int sequence_to_network = htonl(sequence);
    int unicast_request_size = request_length + (2 * sizeof(int)) + (2 * sizeof(char));
    int bytes_received;

    ABORT_FLAG = false;
    JOIN_THREAD = false;

    // Buffer to Send
    unicast_request = (void *) malloc(unicast_request_size); 
    if(!unicast_request){
        exit(EXIT_FAILURE);
    }
    //Send unicast socket
    //sprintf(unicast_request, "%d:%d:%s", sequence, service_id, (char *) request_buffer);

    //Initialize buffers
    memset(unicast_request, 0, unicast_request_size);
    memset(unicast_ping_response, 0, MESSAGE_LENGTH * sizeof(char));
    memset(unicast_ack, 0, MESSAGE_LENGTH * sizeof(char));

    // Set Request Header and Payload to Send
    memcpy(unicast_request, &sequence_to_network, sizeof(int));
    memcpy(unicast_request + sizeof(int), seperator, sizeof(char));
    memcpy(unicast_request + sizeof(int) + sizeof(char), &service_id_to_network, sizeof(int));
    memcpy(unicast_request + sizeof(int) + sizeof(char) + sizeof(int), seperator, sizeof(char));
    memcpy(unicast_request + sizeof(int) + sizeof(char) + sizeof(int) + sizeof(char), request_buffer, request_length);

    
    for(int i = 0; i < TRIES; i++) {
        sendto(unicast_socket_fd, unicast_request, request_length + 2 * sizeof(int) + 2 * sizeof(char), 0, (struct sockaddr *) &unicast_server_address, sizeof(unicast_server_address));
        //printf("\033[0;33mClient send Unicast packet on Server: %s at %d\n\033[0m", inet_ntoa((struct in_addr) unicast_server_address.sin_addr), ntohs(unicast_server_address.sin_port));
        memset(unicast_ack, 0, MESSAGE_LENGTH * sizeof(char));
        if(!check_polling(&unicast_poll_information, unicast_socket_fd, TIMEOUT)){
            continue;
        }

        if (recvfrom(unicast_socket_fd, (void *) unicast_ack, MESSAGE_LENGTH, MSG_WAITALL, (struct sockaddr *) &unicast_ping_server_address, &length) < 0) {
            perror("recvfrom ack failed");
            exit(EXIT_FAILURE);
        }

        if(!strcmp(unicast_ack, "ACK")) {
            break;
        }
        else if(!strcmp(unicast_ping_response, "PING")) {
            // Send
            i--;
            sendto(unicast_socket_fd, acknowledgement, strlen(acknowledgement) * sizeof(char), 0, (struct sockaddr *) &unicast_ping_server_address, sizeof(unicast_ping_server_address));
        }
    }

    if(!(*unicast_ack)) {
        return -1; // unicast request not ack from server
    }

    // Monitor server status (keepalive (ping))
    ping_arguments.unicast_ping_server_address = unicast_ping_server_address;
    ping_arguments.service_id = service_id;
    pthread_create(&ping_server_thread, NULL, ping_server, &ping_arguments);
    

    // Wait for response or late ACKs
    while(!ABORT_FLAG) {
        memset(unicast_ping_response, 0, sizeof(char) * MESSAGE_LENGTH);
        bytes_received = 0;

        if(!check_polling(&unicast_poll_information, unicast_socket_fd, TIMEOUT)){
            continue;
        }

        //Receive from server the answer
        if ((bytes_received = recvfrom(unicast_socket_fd, (void *) unicast_ping_response, MESSAGE_LENGTH, MSG_WAITALL, (struct sockaddr *) &unicast_ping_server_address, &length)) < 0) {
            perror("recvfrom failed");
            exit(EXIT_FAILURE);
        }
        
        // ACKs that arrived with latency 
        if(!strcmp(unicast_ping_response, "ACK")) {
            continue;
        }
        else if(!strcmp(unicast_ping_response, "PING")) {
            // Send
            sendto(unicast_socket_fd, acknowledgement, strlen(acknowledgement) * sizeof(char), 0, (struct sockaddr *) &unicast_ping_server_address, sizeof(unicast_ping_server_address));
            continue;
        }
        
        *response_length = bytes_received;

        // send ack to server
        sendto(unicast_socket_fd, acknowledgement, strlen(acknowledgement) * sizeof(char), 0, (struct sockaddr *) &unicast_ping_server_address, sizeof(unicast_ping_server_address));

        // Data was received
        break;
    
    }

    // Ping finishes here
    JOIN_THREAD = true;
    pthread_join(ping_server_thread, NULL);
    
    if(ABORT_FLAG) {
        return -2; // no ack from server in ping
    }
      
    memccpy(response_buffer,(void *) unicast_ping_response, 0, *response_length);
    sequence++;

    return 0;
}


int RequestReply (int service_id, void *request_buffer, int request_length, void *response_buffer, int *response_length){
    struct sockaddr_in unicast_server_address;
    int multicast_status, unicast_status;
    
    
    // Multicast
    multicast_status = multicast_discovery(service_id, &unicast_server_address);
    if(multicast_status == -2){
        printf("\033[0;31m[ERROR]: No Available Servers Found\n\033[0m");
        return -1;
    }
    else if(multicast_status == -1){
        printf("\033[0;31m[ERROR]: No Available Services Found\n\033[0m");
        return -1;
    }
    else {
        printf("\033[0;33mServer Information: %s at %d\n\033[0m", inet_ntoa((struct in_addr) unicast_server_address.sin_addr), ntohs(unicast_server_address.sin_port));
    }
    
    // Unicast and Ping
    unicast_status = unicast_communication(service_id, request_buffer, request_length, response_buffer, response_length, unicast_server_address);
    if(unicast_status == -2) {
        printf("\033[0;31m[ERROR]: No Ping Response\n\033[0m");
        return -1;
    }
    else if(unicast_status == -1) {
        printf("\033[0;31m[ERROR]: Unicast Server did not Respond\n\033[0m");
        return -1;
    }


    return 0;
}