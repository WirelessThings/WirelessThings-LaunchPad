#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Simple UDP broadcast sender for Language of Things

    Send WirelessMessage Json via UDP broadcasts on port 50141

    In this case we send two message to device MA via ALL Message Bridges on the local network

    Copyright 2015 Ciseco Ltd.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

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

jsonDict = {
    'type': "WirelessMessage",
    'network': "ALL",               # could be 'Serial' or 'ALL'
    'id': "MA",                     # sending to example device ID of MA
    'data': [                       # sending two commands HELLO and TEMP
        "HELLO",                    # this will result in two message going out via the radio
        "TEMP"                      # aMAHELLO---- and aMATEMP-----
    ]
}

jsonout = json.dumps(jsonDict)
try:
    sock.sendto(jsonout.encode(), ('<broadcast>', TO_PORT))
except socket.error as msg:
    if msg[0] == 101:
        try:
            sock.sendto(jsonout.encode(), ('127.0.0.255', TO_PORT))
        except socket.error as msg:
            print(("Failed to send, Error code : {} Message: {}".format(msg[0], msg[1])))
        else:
            print(("Sent: {}".format(jsonout)))
    else:
        print(("Failed to send, Error code : {} Message: {}".format(msg[0], msg[1])))
else:
    print(("Sent: {}".format(jsonout)))

sock.close()
