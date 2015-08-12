#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast sender for Language of Things

    Send WirelessMessage Json via UDP broadcasts on port 50141

    Uasge
    $ python commandUDPSend.py -- HELLO
    or
    $ ./commnadUDPSend.py MA TEMP

    Optionally you can speficy a network via a third argument

    $ ./commandUDPSend.py MA TEMP Serial


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

if len(sys.argv) == 2:
    print("You need to speficy a Language of Things device ID and messgae to send")
    sys.exit()

jsonDict = {'type':"WirelessMessage"}

if len(sys.argv) == 4:
    jsonDict['network'] = sys.argv[3]
else:
    jsonDict['network'] = "ALL"      # could be 'Serial' or 'ALL'

jsonDict['id'] = sys.argv[1].upper()
jsonDict['data'] = [sys.argv[2].upper()]

jsonout = json.dumps(jsonDict)

sock.sendto(jsonout, ('<broadcast>', TO_PORT))
print("Sent: {}".format(jsonout))
sock.close()
