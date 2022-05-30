#SIMPLESCRIPT
SET $a 0


#label
SND 1 $a
PRN 1 -> $a

RCV 1 $response
PRN 1 <- $response


ADD $a $response 1

SLP 2
BRA #label