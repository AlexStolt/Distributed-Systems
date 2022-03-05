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
  Server(const char *PORT, struct addrinfo *hints);

  // Getters
  const char *get_port() const;
  int get_socket_fd() const;
  void display_address() const;

  // Methods
  
  void enable_polling(int socket_fd);
  bool check_polling(int socket_fd, int timeout);

private:
  const char *port;
  int backlog;
  struct addrinfo *hints;
  struct addrinfo *server_info;
  char ipv4_address[INET_ADDRSTRLEN];
  char ipv6_address[INET6_ADDRSTRLEN];

protected:
  void get_address_info();
  void bind_server();

  // Poll related helper data and methods
  poll_information_t poll_information;
  void disable_blocking(int socket_fd);
  void pfds_init();
  void pfds_add(int socket_fd);

  // Bound socket
  int socket_fd;
};

#endif
