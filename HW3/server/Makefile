all:  nfs_server_app.o nfs_server_utils.o helper_utils.o nfs.h
	gcc -g -Wall nfs_server_app.o nfs_server_utils.o helper_utils.o -o server.out -lpthread -lm
	
nfs_server_app.o: nfs_server_app.c nfs.h
	gcc -g -Wall -c nfs_server_app.c -o nfs_server_app.o -lpthread -lm

nfs_server_utils.o: nfs_server_utils.c nfs.h
	gcc -g -Wall -c nfs_server_utils.c -o nfs_server_utils.o -lpthread -lm

helper_utils.o: helper_utils.c nfs.h
	gcc -g -Wall -c helper_utils.c -o helper_utils.o -lpthread -lm

clean:
	rm *.o *.out