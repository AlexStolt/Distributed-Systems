#include "client_api.h"

#define MINIMUM_NUMBER_OF_PRIMES 2
#define MAXIMUM_NUMBER_OF_PRIMES 10
#define MAXIMUM_VALUE 100

#define SERVICE 20

int main(int argc, char const *argv[]) {
    int number_of_primes;
    //char reqbuf[] = "Hello From Client";
    char rsvbuf[1024] = "";
    char rcvbuf[1024] = "31";
    int number;
    
    api_init();

    // Random Number Generator Seed
    srand(time(NULL));
    number_of_primes = rand() % MAXIMUM_NUMBER_OF_PRIMES;
    number_of_primes = number_of_primes < MINIMUM_NUMBER_OF_PRIMES ? MINIMUM_NUMBER_OF_PRIMES : number_of_primes;

    for(int i = 0; i < number_of_primes; i++){
        number = rand() % MAXIMUM_VALUE; 
        printf("Prime to Calculate: %d", number);
        RequestReply(SERVICE, (void *) &number, sizeof(int), (void *) rsvbuf, NULL);
    }




    return 0;
}
