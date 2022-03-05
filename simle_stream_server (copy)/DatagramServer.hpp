#ifndef __DATAGRAMSERVER_HPP_
#define __DATAGRAMSERVER_HPP_

#include "Header.hpp"
#include "ServerUtilities.hpp"

class DatagramServer : public Server {
public:
  // Create a Simple Datagram (UDP) Server
  DatagramServer(const char *PORT, struct addrinfo *hints);

  // Create a Multicast Datagram (UDP) Server
  DatagramServer(const char *MULTICAST_PORT, struct addrinfo *multicast_hints, char *multicast_address, char *interface, const char *UNICAST_PORT, struct addrinfo *unicast_hints);
  
  bool register_service(int service_id);
  void display_services();
  bool check_service(int service_id);

  // Server - Client Discovery
  void multicast_discovery();


protected:
  int receive_buffer(struct sockaddr_storage& client_address, char *buffer);
  int send_buffer(struct sockaddr_storage& client_address, char *buffer);
  std::vector<int> services;

  int unicast_socket_fd;
};

#endif