1)
multiply.txt 
------------
* Takes as arguments two integers <a> and <b>
* Calculates the product via addition
* Assumes <a> is >= 0, else terminates

Example:
run multiply.txt 5 15

2) 
sender.txt
----------
* Takes as arguments an integer <tid>, an integer <cnt>, a text message <msg> and an integer <time> 
* Waits <time> seconds and sends to thread <tid> the message <msg>
* This is repeated <cnt> times  

receiver.txt
------------
* Takes as arguments an integer <tid> and an integer <cnt>
* Receives from thread <tid> a text message and prints it 
* This is repeated <cnt> times 

Example
run sender.txt 1 3 "hello there" 5 || receiver.txt 0 3

3)
ring.txt
--------
* Takes as arguments three integers <myid>, <nxtid>, <prvid>, an integer <cnt> and an integer <time>
* Sends along a ring, according to <nxtid> and <prvid>, a token with an initial value of 1
* The token value is incremented after each hop
* Forwarding is done after a delay of <time> seconds
* The token makes <cnt> circles around the ring   

Example
run ring.txt 0 1 2 10 3 || ring.txt 1 2 0 10 3 || ring.txt 2 0 1 10 3