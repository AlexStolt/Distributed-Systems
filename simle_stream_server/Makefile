all: server_utils.o datagram_server.o main.o
	g++ -g -Wall server_utils.o datagram_server.o main.o -o a.out
	make clean

server_utils.o: ServerUtilities.cpp ServerUtilities.hpp DatagramServer.hpp Header.hpp
	g++ -g -Wall -c ServerUtilities.cpp -o server_utils.o


datagram_server.o: DatagramServer.cpp ServerUtilities.hpp DatagramServer.hpp Header.hpp
	g++ -g -Wall -c DatagramServer.cpp -o datagram_server.o

main.o: main.cpp Header.hpp ServerUtilities.hpp DatagramServer.hpp
	g++ -g -Wall -c main.cpp -o main.o

clean: 
	rm *.o