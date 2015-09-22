#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Filterd UDP lienter

    listen for UDP broadcasts on port 50140
    and filters by give ID and network if passed on the command line

    usage
    $ python filterUDPListen.py
    or
    $ ./filterUDPListen.py

    Optionally
    $ ./filterUDPListen.py MA Serial

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

sock.bind(('', FROM_PORT))
lasttime = time()

while True:
    data, addr = sock.recvfrom(1024*8)
    pydata = json.loads(data)
    if pydata['type'] == 'WirelessMessage':
        if len(sys.argv) == 3:
            if pydata['network'] != sys.argv[2]:
                continue
        if len(sys.argv) == 2:
            if pydata['id'] == sys.argv[1]:
		now = time()
                timediff = now - lasttime
		lasttime = now
                print("Device: {} Data: {} Time: {} Network: {} Timesince: {}".format(pydata['id'], pydata['data'][0], pydata['timestamp'], pydata['network'], timediff))
        else:
            print("Device: {} Data: {}".format(pydata['id'], pydata['data'][0]))
