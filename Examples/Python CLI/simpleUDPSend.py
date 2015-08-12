#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast sender for Language of Things

    Send WirelessMessage Json via UDP broadcasts on port 50141

    In this case we send two message to device MA via ALL Message Bridges on the local network

"""
import sys
from time import time, sleep
import os
import socket
import json

FROM_PORT = 50140
TO_PORT = 50141

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP

sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
if sys.platform == 'darwin':
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

jsonDict = {'type':"WirelessMessage"}
jsonDict['network'] = "All"      # could be 'Serial' or 'ALL'
jsonDict['id'] = "MA"               # sending to example device ID of MA
jsonDict['data'] = ["HELLO","TEMP"] # sending two commands HELLO and TEMP
                                    # this will result in two message going out via the radio
                                    # aMAHELLO---- and aMATEMP-----

jsonout = json.dumps(jsonDict)

sock.sendto(jsonout, ('<broadcast>', TO_PORT))
print("Sent: {}".format(jsonout))
sock.close()
