import pickle
import socket
import sys

PACKET_LENGTH   = 1024

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('python3 load_balancer.py <IP> <PORT>')
        exit(0)

    LOAD_BALANCER_IP    = sys.argv[1]
    LOAD_BALANCER_PORT  = int(sys.argv[2])



    # TCP Listener Socket
    tcp_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_fd.bind((LOAD_BALANCER_IP, LOAD_BALANCER_PORT))
    tcp_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_fd.listen()




    while True:
        connection, client_address = tcp_fd.accept()
        with connection:
            # Hosts Requests the Baton
            deserialized_data = connection.recv(PACKET_LENGTH)
            if not deserialized_data:
                continue
            deserialized_data = pickle.loads(deserialized_data)
            # Give the Baton to Host
            if deserialized_data['request_type'] != 'baton_acquire_request':
                connection.send('NACK'.encode())
                continue
            
            connection.send('ACK'.encode())

            
            # Retrieve Baton from Host
            deserialized_data = connection.recv(PACKET_LENGTH)
            if not deserialized_data:
                continue
            deserialized_data = pickle.loads(deserialized_data)

            # Verify that the Button was Retrieved
            if deserialized_data['request_type'] != 'baton_release_request':
                connection.send('NACK'.encode())
                continue

            connection.send('ACK'.encode())




