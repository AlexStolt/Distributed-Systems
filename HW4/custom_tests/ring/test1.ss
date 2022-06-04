#SIMPLESCRIPT
SET $a 0

#label

SND 1 $a
PRN $a

SLP 1

RCV 2 $response

ADD $a $response 1

BRA #label