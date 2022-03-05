#include "DatagramServer.hpp"

// Constructors
DatagramServer::DatagramServer(const char *PORT, struct addrinfo *hints) : Server(PORT, hints) {
  get_address_info();
  bind_server();
}

DatagramServer::DatagramServer(const char *MULTICAST_PORT, struct addrinfo *multicast_hints, 
                               char *multicast_address, char *interface, const char *UNICAST_PORT, 
                               struct addrinfo *unicast_hints) 
                               : DatagramServer(MULTICAST_PORT, multicast_hints){
  
  struct ip_mreq group;
  int reuse;
  int status;
  struct addrinfo *server_info;
  struct addrinfo *iter_ptr;


  // Multicast Socket for Discovery
  group.imr_multiaddr.s_addr = inet_addr(multicast_address);
  group.imr_interface.s_addr = inet_addr(interface);

  if(setsockopt(socket_fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, (char *) &group, sizeof(group)) == -1){
    std::cerr << "Error in setsockopt() for multicast" << std::endl; 
    close(socket_fd);
    exit(EXIT_FAILURE);
  }

  
  // Unicast Socket for Unicast Communication
  if ((status = getaddrinfo(NULL, UNICAST_PORT, unicast_hints, &server_info)) != 0) {
    std::cerr << "Get Address Info Status: %s " << gai_strerror(status) << std::endl;
    exit(EXIT_FAILURE);
  }


  // Loop through all the results and bind to the first we can
  for(iter_ptr = server_info; iter_ptr != NULL; iter_ptr = iter_ptr->ai_next){

    // Create a Unicast Socket
    if ((unicast_socket_fd = socket(iter_ptr->ai_family, iter_ptr->ai_socktype, iter_ptr->ai_protocol)) == -1){
      std::cerr << "Error in socket()" << std::endl;
      continue;
    }

    // Set options for reusable port
    if (setsockopt(unicast_socket_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(int)) == -1){
      close(unicast_socket_fd);
      std::cerr << "Error in setsockopt()" << std::endl;
      continue;
    }

    if (bind(unicast_socket_fd, iter_ptr->ai_addr, iter_ptr->ai_addrlen) == -1) {
      close(unicast_socket_fd);
      std::cerr << "Error in bind()" << std::endl;
      continue;
    }
     break;
  }

  if (!iter_ptr){
    std::cerr << "Server failed to bind" << std::endl;
    exit(EXIT_FAILURE);
  }
}

bool DatagramServer::register_service(int service_id){
  //int result;
  std::vector<int>::iterator iterator;

  iterator = std::find(services.begin(), services.end(), service_id);
  if(iterator != services.end()){
    return false;
  }

  // Insert service at the tail of the vector
  services.insert(services.end(), service_id);
  
  return true;  
}

void DatagramServer::display_services() {
  std::vector<int>::iterator iterator;

  for (iterator = services.begin(); iterator < services.end(); iterator++)
    std::cout << *iterator << ' ';
  std::cout << '\n';
}


// Server - Client Discovery Handshake
void DatagramServer::multicast_discovery(){
  char request[MAX_MESSAGE_LENGTH];
  char response[MAX_MESSAGE_LENGTH];
  int flags = 0;
  struct sockaddr client_address;
  socklen_t client_address_length = sizeof(client_address);
  int bytes_received;
  int bytes_sent;
  
  while (1){
    std::memset(request, 0, MAX_MESSAGE_LENGTH * sizeof(char));
    bytes_received = recvfrom(socket_fd, request, MAX_MESSAGE_LENGTH * sizeof(char), flags, &client_address, &client_address_length);
    if(bytes_received < 0){
      exit(EXIT_FAILURE);
    }
    else if(!bytes_received){
      // Connection Closed by Client
      continue;
    }

    std::cout << request;
    // Get Server Load
    // get_load()
    //

    std::memset(response, 0, MAX_MESSAGE_LENGTH * sizeof(char));
    std::strcat(response, "MULTICAST OFFER");
    std::cout << response << std::endl;
    bytes_sent = sendto(socket_fd, response, strlen(response) * sizeof(char), flags, &client_address, client_address_length);

    
  }
  
  

}






// Receive a buffer from a client and return the amount of bytes received 
int DatagramServer::receive_buffer(struct sockaddr_storage& client_address, char *buffer){
  int bytes_received;
  socklen_t client_address_length = sizeof(client_address);

  // Set NULL buffer
  std::memset(buffer, 0, MAX_MESSAGE_LENGTH * sizeof(char));

  // Receive
  if((bytes_received = recvfrom(socket_fd, buffer, MAX_MESSAGE_LENGTH - 1, 0, (struct sockaddr *) &client_address, &client_address_length)) == -1) {
    perror("Error in recvfrom()");
    exit(EXIT_FAILURE);
  }
  
  return bytes_received;
}


// Send buffer to client and return the number of bytes sent
int DatagramServer::send_buffer(struct sockaddr_storage& client_address, char *buffer){
  int bytes_sent;
  socklen_t client_address_length = sizeof(client_address);

  if((bytes_sent = sendto(socket_fd, buffer, std::strlen(buffer), 0, (struct sockaddr *) &client_address, client_address_length)) == -1) {
    perror("Error in sendto()");
    exit(EXIT_FAILURE);
  }

  return bytes_sent;
}


