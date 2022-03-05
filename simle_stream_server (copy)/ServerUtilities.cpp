#include "ServerUtilities.hpp"

// Constructor
Server::Server(const char *PORT, struct addrinfo *HINTS) : port(PORT), hints(HINTS){
  std::memset(ipv4_address, 0, INET_ADDRSTRLEN * sizeof(char));
  std::memset(ipv6_address, 0, INET6_ADDRSTRLEN * sizeof(char));

  get_address_info();
  bind_server();
}


// Getters
const char *Server::get_port() const {
  return port;
}

int Server::get_socket_fd() const {
  return socket_fd;
}

void Server::get_address_info(){
  int status;
  
  if ((status = getaddrinfo(NULL, port, hints, &server_info)) != 0) {
    std::cerr << "Get Address Info Status: %s " << gai_strerror(status) << std::endl;
    exit(EXIT_FAILURE);
  }
}  

void Server::display_address() const {
  if(*ipv4_address){
    std::cout << "Socket Bind: Local IPv4: " << ipv4_address << " at " << port << std::endl;
  }
  if(*ipv6_address){
    std::cout << "Socket Bind: Local IPv6: " << ipv6_address << " at " << port << std::endl;
  }
}

// Bind server to specified port
void Server::bind_server(){
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


  // IPv4
  if(iter_ptr->ai_family == AF_INET){
    struct sockaddr_in *ipv4 = (struct sockaddr_in *) iter_ptr->ai_addr;
    inet_ntop(iter_ptr->ai_family, &(ipv4->sin_addr), ipv4_address, INET_ADDRSTRLEN);
  }
  else if (iter_ptr->ai_family == AF_INET6){
    struct sockaddr_in6 *ipv6 = (struct sockaddr_in6 *) iter_ptr->ai_addr;
    inet_ntop(iter_ptr->ai_family, &(ipv6->sin6_addr), ipv6_address, INET6_ADDRSTRLEN);
  }

  freeaddrinfo(server_info);
}

// Poll related information
void Server::pfds_init(){
  poll_information.pfds = new struct pollfd[poll_information.pfds_size];
  if(!poll_information.pfds){
    close(socket_fd);
    exit(EXIT_FAILURE);
  }
}

void Server::pfds_add(int socket_fd){
  if(poll_information.nfds >= poll_information.pfds_size){
    std::cerr << "Socket can not be added to polling array" << std::endl;
    close(socket_fd);
    exit(EXIT_FAILURE);
  }

  // Add socket to poll
  poll_information.pfds[poll_information.nfds].fd = socket_fd;
  poll_information.pfds[poll_information.nfds].events = POLLIN;
  
  // Increment count of sockets in poll
  poll_information.nfds++;
}

void Server::disable_blocking(int socket_fd){
  int flags = fcntl(socket_fd, F_GETFL);

  // Set to Non-Blocking Socket
  flags |= O_NONBLOCK;
  fcntl(socket_fd, F_SETFL, flags);
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