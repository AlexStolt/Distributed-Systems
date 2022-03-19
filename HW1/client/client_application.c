#include "client_api.h"

#define NUMBER_OF_PRIMES 20
#define MAXIMUM_VALUE 100

#define SERVICE 20

int main(int argc, char const *argv[]) {
    clock_t start, end;
    double computation_time;
    char receive_buffer[1024];  
    int receive_buffer_length;
    int number_of_primes = NUMBER_OF_PRIMES;
    int upper_limit = MAXIMUM_VALUE;
    int number;
    int number_to_network;
    int status;
    
    // Initialize the API
    api_init();

    if(argc == 2){
        number_of_primes = atoi(argv[1]);
    }
    else if(argc == 3){
        upper_limit = atoi(argv[2]);
    }
    
    for(int i = 0; i < number_of_primes; i++){
        memset(receive_buffer, 0, MESSAGE_LENGTH * sizeof(char));
        receive_buffer_length = 0;

        srand(time(NULL));
        number = rand() % upper_limit; 
        number_to_network = htonl(number); 

        printf("Prime to Calculate: %d\n", number);
        start = clock();
        status = RequestReply(SERVICE, (void *) &number_to_network, sizeof(int), (void *) receive_buffer, &receive_buffer_length);
        end = clock();
        
        if (status < 0){
            continue;
        }
        
        computation_time = ((double) (end - start)) / CLOCKS_PER_SEC;
        printf("\033[0;32m%s Computed in %lf Seconds\n\033[0m", receive_buffer, computation_time);
    
    }




    return 0;
}
