#SIMPLESCRIPT
SET $a 0

#label

SND 1 $a
PRN $a

SLP 1

RCV 2 $response

ADD $a $response 1

BGE $a 20 #flawed_label

BRA #label



#flawed_label
ADD $b $b 1