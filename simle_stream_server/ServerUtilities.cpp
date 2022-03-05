#include "ServerUtilities.hpp"

// Get Server InformationInformation 
struct addrinfo *Server::get_address_info(const char *port, const struct addrinfo *hints){
  struct addrinfo *server_info;
  int status;

  if ((status = getaddrinfo(NULL, port, hints, &server_info)) != 0) {
    std::cerr << "Get Address Info Status: %s " << gai_strerror(status) << std::endl;
    exit(EXIT_FAILURE);
  }

  return server_info;
}


// Bind server to specified port
int Server::bind_server(struct addrinfo *server_info){
  int socket_fd;
  struct addrinfo *iter_ptr;
  int reuse = 1;

  // Loop through all the results and bind to the first we can
  for(iter_ptr = server_info; iter_ptr != NULL; iter_ptr = iter_ptr->ai_next){

    // Get socket file descriptor
    if ((socket_fd = socket(iter_ptr->ai_family, iter_ptr->ai_socktype, iter_ptr->ai_protocol)) == -1) {
      std::cerr << "Error in socket()" << std::endl;
      continue;
    }

    // Set options for reusable port
    if (setsockopt(socket_fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(int)) == -1) {
      std::cerr << "Error in setsockopt()" << std::endl;
      exit(EXIT_FAILURE);
    }

    // Try to bind socket to port
    if (bind(socket_fd, iter_ptr->ai_addr, iter_ptr->ai_addrlen) == -1) {
      close(socket_fd);
      std::cerr << "Error in bind()" << std::endl;
      continue;
    }

    break;
  }

  if (!iter_ptr){
    std::cerr << "Server failed to bind" << std::endl;
    exit(EXIT_FAILURE);
  }

  freeaddrinfo(server_info);

  return socket_fd;
}

// Multicast Membership Add
void Server::multicast_membership_join(int socket_fd, const char *multicast_address, const char *interface){
  struct ip_mreq group;

  // Multicast Socket for Discovery
  group.imr_multiaddr.s_addr = inet_addr(multicast_address);
  group.imr_interface.s_addr = inet_addr(interface);

  if(setsockopt(socket_fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, (char *) &group, sizeof(group)) == -1){
    std::cerr << "Error in setsockopt() for multicast" << std::endl; 
    close(socket_fd);
    exit(EXIT_FAILURE);
  }
}

// Poll related information
void Server::pfds_init(){
  poll_information.pfds = new struct pollfd[poll_information.pfds_size];
  if(!poll_information.pfds){
    exit(EXIT_FAILURE);
  }
}

void Server::disable_blocking(int socket_fd){
  int flags = fcntl(socket_fd, F_GETFL);

  // Set to Non-Blocking Socket
  flags |= O_NONBLOCK;
  fcntl(socket_fd, F_SETFL, flags);
}

void Server::pfds_add(int socket_fd){
  if(poll_information.nfds >= poll_information.pfds_size){
    std::cerr << "Socket was not added to polling array" << std::endl;
    exit(EXIT_FAILURE);
  }

  // Add socket to poll
  poll_information.pfds[poll_information.nfds].fd = socket_fd;
  poll_information.pfds[poll_information.nfds].events = POLLIN;
  
  // Increment count of sockets in poll
  poll_information.nfds++;
}

void Server::enable_polling(int socket_fd){
  // Initialize polling array 
  pfds_init();
  
  // Non-Blocking socket
  disable_blocking(socket_fd);
  pfds_add(socket_fd);
}

bool Server::check_polling(int socket_fd, int timeout){
  int events = poll(poll_information.pfds, poll_information.nfds, timeout);
  int polling;

  if(!events){
    return false;
  }

  for(nfds_t i = 0; i < poll_information.nfds; i++){
    if(poll_information.pfds[i].fd != socket_fd){
      continue;
    }
    polling = poll_information.pfds[i].revents & POLLIN;
    if(!polling){
      return false;
    }
    else {
      return true;
    }
  }  

  return false;
}