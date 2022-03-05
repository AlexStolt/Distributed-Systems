#ifndef __DATAGRAMSERVER_HPP_
#define __DATAGRAMSERVER_HPP_

#include "Header.hpp"
#include "ServerUtilities.hpp"

class DatagramServer : public Server {
public:
  // Create and Bind a Multicast Socket 
  int socket_init(const char *port, struct addrinfo *hints);
  


  bool register_service(int service_id);
  void display_services();
  bool check_service(int service_id);

  // Server - Client Discovery
  void multicast_discovery(int socket_fd);


protected:
  int receive_buffer(struct sockaddr_storage& client_address, char *buffer);
  int send_buffer(struct sockaddr_storage& client_address, char *buffer);
  std::vector<int> services;

  int unicast_socket_fd;
};

#endif