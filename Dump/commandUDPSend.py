#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast sender for LLAP
    
    Send LLAP Json via UDP broadcasts on port 50141
    
    Uasge
    $ python commandUDPSend.py -- HELLO
    or
    $ ./commnadUDPSend.py MA TEMP
    
"""
import sys
from time import time, sleep
import os
import socket
import json

LLAP_FROM_PORT = 50140
LLAP_TO_PORT = 50141

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP

sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

if len(sys.argv) == 2:
    print("You need to speficy a llap ID and messgae to send")
    sys.exit()

jsonDict = {'type':"LLAP"}
if len(sys.argv) == 4:
    jsonDict['network'] = sys.argv[3]
else:
    jsonDict['network'] = "Serial"      # could be 'Serial' or 'ALL'

jsonDict['id'] = sys.argv[1].upper()
jsonDict['data'] = [sys.argv[2].upper()]

jsonout = json.dumps(jsonDict)

print("Sent: {}".format(jsonout))

sock.sendto(jsonout, ('<broadcast>', LLAP_TO_PORT))

sock.close()
