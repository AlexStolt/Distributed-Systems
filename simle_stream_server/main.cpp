#include <iostream>
#include "Header.hpp"
#include "DatagramServer.hpp"
#include "ServerUtilities.hpp"


#define MULTICAST_PORT "3456"
#define UNICAST_PORT "5555"
#define BACKLOG 10
#define PORT 8888


int main(int argc, char const *argv[]){
  struct addrinfo mcast_hints;
  struct addrinfo ucast_hints;
  DatagramServer *server;
  char *hello = "Hello from server\n";
  struct sockaddr_in clientaddr;
  

  std::memset(&mcast_hints, 0, sizeof mcast_hints);
  
  mcast_hints.ai_family = AF_INET; // AF_INET or AF_INET6 to force version
  mcast_hints.ai_socktype = SOCK_DGRAM;
  mcast_hints.ai_flags = AI_PASSIVE;

  std::memset(&ucast_hints, 0, sizeof ucast_hints);
  
  ucast_hints.ai_family = AF_INET; // AF_INET or AF_INET6 to force version
  ucast_hints.ai_socktype = SOCK_DGRAM;
  ucast_hints.ai_flags = AI_PASSIVE;


  char multitcast[] = "225.1.1.1";
  char local[] = "192.168.1.5"; // sudo ifconfig lo multicast
  server = new DatagramServer();
  int mcast_socket = server->socket_init(MULTICAST_PORT, &mcast_hints);
  
  server->multicast_membership_join(mcast_socket, multitcast, local);

  char buffer[1024];
  memset(buffer, 0, 1024 * sizeof(char));
  struct sockaddr client;
  socklen_t size = sizeof(client);

  // Filling server information
  clientaddr.sin_family = AF_INET;
  clientaddr.sin_port = htons(PORT);
  clientaddr.sin_addr.s_addr = inet_addr("127.0.0.1");;

  int ucast = server->socket_init(MULTICAST_PORT, &mcast_hints);

  server->multicast_discovery(mcast_socket);
  //sendto(server->get_socket_fd() , (const char *)hello, strlen(hello), MSG_CONFIRM, (const struct sockaddr *) &clientaddr, sizeof(clientaddr));

  // recvfrom(server->get_socket_fd(), buffer, 1024 * sizeof(char), 0, &client, &size);
  // std::cout << buffer;
  // memset(buffer, 0, 1024 * sizeof(char));
  
  return 0;
}
