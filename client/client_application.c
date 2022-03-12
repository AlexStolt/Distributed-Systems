#include "client_api.h"

int main(int argc, char const *argv[]) {
    //char reqbuf[] = "Hello From Client";
    char rsvbuf[1024] = "";
    char number = '3';
    
    api_init();
    
    int i  = 0;
    //while(i < 5) {
        RequestReply(20, (void *) &number, sizeof(char), (void *) rsvbuf, strlen(rsvbuf));
        printf("%s\n", rsvbuf);
        i++;
    //}

    return 0;
}
