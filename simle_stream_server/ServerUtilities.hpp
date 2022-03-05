#ifndef __SERVERUTILITIES_HPP_
#define __SERVERUTILITIES_HPP_

#include "Header.hpp"

// Poll Information
typedef struct {
public:
  nfds_t nfds = 0;
  nfds_t pfds_size = PFDS_SIZE;
  struct pollfd *pfds;
} poll_information_t;
 

// Basic Server Utilities 
class Server {
public:
  void multicast_membership_join(int socket_fd, const char *multicast_address, const char *interface);  

  // Methods
  void enable_polling(int socket_fd);
  bool check_polling(int socket_fd, int timeout);

protected:
  
  struct addrinfo * get_address_info(const char *port, const struct addrinfo *hints);
  int bind_server(struct addrinfo *server_info);

  // Poll related helper data and methods
  poll_information_t poll_information;
  void pfds_init();
  void disable_blocking(int socket_fd);
  void pfds_add(int socket_fd);

};

#endif
