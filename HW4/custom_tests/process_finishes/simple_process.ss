#SIMPLESCRIPT


PRN Counting from $argv1 to $argv2 with Step $argv3

#LOOP:  BGE $argv1 $argv2 #RETURN  
        
        PRN $argv1
        
        ADD $argv1 $argv1 $argv3
        SLP 2

        BRA #LOOP


#RETURN RET