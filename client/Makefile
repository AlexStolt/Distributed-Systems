client: client_application.o client_api.o 
	gcc client_application.o client_api.o -Wall -g -o client -lpthread
client_application.o: client_application.c
	gcc client_application.c -Wall -g -c -o client_application.o
client_api.o: client_api.c
	gcc client_api.c -Wall -g -c -o client_api.o
clean: 
	rm *.o

benchmark:
	./client &
	./client &
	./client &
	./client &
	./client &
	./client