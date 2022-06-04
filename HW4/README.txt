############################# How to Run #############################
1. Load Balancing Deactivated (LOAD_BALANCE Flag in environment.py is False)
* python3 environment.py

2. Load Balancing Activated (LOAD_BALANCE Flag in environment.py is True)
* python3 load_balancer.py <IP> <PORT>
* python3 environment.py <IP> <PORT>


[Notes]: The Load Balancing is Activated by Default

############################# [Custom Tests] #############################

# test_0: Simple Ring with Three Nodes that Count 
run custom_tests/ring/test1.ss||run custom_tests/ring/test2.ss||run custom_tests/ring/test3.ss

# test1: Simple Ring with Syntax Error on the First Node (test1)
run custom_tests/ring_errors/test1.ss||run custom_tests/ring_errors/test2.ss||run custom_tests/ring_errors/test3.ss


# Simple Ring and Some Processes Finish Earlier
run custom_tests/ring/test1.ss||run custom_tests/ring/test2.ss||run custom_tests/ring/test3.ss
run custom_tests/process_finishes/simple_process.ss 0 10 2||run custom_tests/process_finishes/simple_process.ss 0 10 2||run custom_tests/process_finishes/simple_process.ss 0 100 2||run custom_tests/process_finishes/simple_process.ss 0 100 2

############################# [Default Tests] #############################

# test0: Multiply Tests
run default_tests/multiply.txt 10 20
run default_tests/multiply.txt 0 20
run default_tests/multiply.txt -1 20

# test1: Sender/Receiver Tests
run default_tests/sender.txt 1 10 "hello there" 5||run default_tests/receiver.txt 0 10

# test2: Sender/Receiver Ring
run default_tests/ring.txt 0 1 2 10 3||run default_tests/ring.txt 1 2 0 10 3||run default_tests/ring.txt 2 0 1 10 3

# Kill Examples
kill 0.0.0.0,56977 0

# List Examples
list 0.0.0.0,56977 1

# Migrate 
migrate 0.0.0.0,38419 0 1 127.0.0.1 50785
