#include "DatagramServer.hpp"

int DatagramServer::socket_init(const char *port, struct addrinfo *hints){
  struct addrinfo *server_info = get_address_info(port, hints);
  return bind_server(server_info);
}




// Server - Client Discovery Handshake
void DatagramServer::multicast_discovery(int socket_fd){
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
// int DatagramServer::receive_buffer(struct sockaddr_storage& client_address, char *buffer){
//   int bytes_received;
//   socklen_t client_address_length = sizeof(client_address);

//   // Set NULL buffer
//   std::memset(buffer, 0, MAX_MESSAGE_LENGTH * sizeof(char));

//   // Receive
//   if((bytes_received = recvfrom(socket_fd, buffer, MAX_MESSAGE_LENGTH - 1, 0, (struct sockaddr *) &client_address, &client_address_length)) == -1) {
//     perror("Error in recvfrom()");
//     exit(EXIT_FAILURE);
//   }
  
//   return bytes_received;
// }


// // Send buffer to client and return the number of bytes sent
// int DatagramServer::send_buffer(struct sockaddr_storage& client_address, char *buffer){
//   int bytes_sent;
//   socklen_t client_address_length = sizeof(client_address);

//   if((bytes_sent = sendto(socket_fd, buffer, std::strlen(buffer), 0, (struct sockaddr *) &client_address, client_address_length)) == -1) {
//     perror("Error in sendto()");
//     exit(EXIT_FAILURE);
//   }

//   return bytes_sent;
// }


