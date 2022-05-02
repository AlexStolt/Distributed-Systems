from requests import request


encoded_request = b'19\x0011\x00LOOKUP\x00_RES4\x00NACK'


def hey(encoded_request):
  fields = []
  
  print(len(encoded_request), len(encoded_request.decode()))
  encoded_request = encoded_request[encoded_request.find(b'\x00') + 1:]
  decoded_request = encoded_request.decode()
  
  
  
  i = 0
  while i < len(decoded_request):
    # Get Length
    len_str = '' 
    while decoded_request[i] != '\x00':
      len_str = len_str + decoded_request[i]
      i = i + 1
    
    # Get Data
    field = ''
    for j in range(int(len_str)):
      field = field + decoded_request[i + j + 1]
    
    fields.append(field.encode())
    i = i + int(len_str) + 1
  
  return fields
  
  
print(hey(encoded_request))