#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
       
int main(int argc, char const *argv[]){
  char buffer[100];
  memset(buffer, 0, 100);
  int fd = open("example.txt", O_RDWR);
  printf("%ld\n", read(fd, buffer, 20));
  printf("%s", buffer);
  write(fd, "WRITTING", 8);




  return 0;
}
