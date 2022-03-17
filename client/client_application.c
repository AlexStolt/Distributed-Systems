#include "client_api.h"

#define NUMBER_OF_PRIMES 100
#define MAXIMUM_NUMBER_OF_PRIMES 40
#define MAXIMUM_VALUE 100

#define SERVICE 20

int main(int argc, char const *argv[]) {
    clock_t start, end;
    double connection_time;
    int number_of_primes;
    //char reqbuf[] = "Hello From Client";
    char rsvbuf[1024] = "";
    char rcvbuf[1024] = "31";
    int number;
    int number_to_network;
    api_init();
    int primes[NUMBER_OF_PRIMES] = {
        4391,4397,4409,4421,4423,4441,4447,4451,4457,4463,
        4481,4483,4493,4507,4513,4517,4519,4523,4547,4549,
        4561,4567,4583,4591,4597,4603,4621,4637,4639,4643,
        4649,4651,4657,4663,4673,4679,4691,4703,4721,4723,
        4729,4733,4751,4759,4783,4787,4789,4793,4799,4801,
        4813,4817,4831,4861,4871,4877,4889,4903,4909,4919
    };


    
    
    
    for(int i = 0; i < NUMBER_OF_PRIMES; i++){
        memset(rsvbuf, 0, MESSAGE_LENGTH * sizeof(char));
        number = primes[i]; 
        number_to_network = htonl(number); 
        //printf("Prime to Calculate: %d\n", number);
        start = clock();
        RequestReply(SERVICE, (void *) &number_to_network, sizeof(int), (void *) rsvbuf, NULL);
        end = clock();
        connection_time = ((double) (end - start)) / CLOCKS_PER_SEC;
        printf("\033[0;32m%s, in time: %f\n\033[0m", rsvbuf, connection_time);
    }




    return 0;
}
