#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
   
#define PORT 3456
#define MAXLINE 1024
   
// Driver code
int main() {
    int sockfd;
    char buffer[MAXLINE];
    char *hello = "Hello from client\n";
    struct sockaddr_in servaddr1;
   
    // Creating socket file descriptor
    if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 ) {
        perror("socket creation failed");
        exit(EXIT_FAILURE);
    }
   
    memset(&servaddr1, 0, sizeof(servaddr1));

    // Filling server information
    servaddr1.sin_family = AF_INET;
    servaddr1.sin_port = htons(PORT);
    servaddr1.sin_addr.s_addr = inet_addr("127.0.0.1");
       
    socklen_t size = sizeof(servaddr1);

    //bind( sockfd, (struct sockaddr *)&clientaddr, sizeof(clientaddr));
       
    int n, len, i = 0;
       
      sendto(sockfd, (const char *)hello, strlen(hello), 0, (const struct sockaddr *) &servaddr1, sizeof(servaddr1));
      recvfrom(sockfd, buffer, 1024 * sizeof(char), 0,(struct sockaddr *)&servaddr1, &size);
      printf("%s\n", buffer);
      //memset(buffer, 0, 1024 * sizeof(char));
  
           
    close(sockfd);
    return 0;
}