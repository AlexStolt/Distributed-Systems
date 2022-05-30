#SIMPLESCRIPT
SET $a 0

#label
SLP 2
RCV 0 $response
PRN 2 <- $response

ADD $a $response 1


SND 0 $a
PRN 2 -> $a

BRA #label




