#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Filterd UDP lienter

    listen for UDP broadcasts on port 50140
    and filters by give ID and network if passed on the command line

    Uasge
    $ python filterUDPListen.py
    or
    $ ./filterUDPListen.py

    Optionally
    $ ./filterUDPListen.py MA Serial

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
    if pydata['type'] == 'LLAP' and pydata['network'] == 'Dashboard': # and pydata['data'][0].startswith("VAL"):
        if len(sys.argv) == 2:
            if pydata['id'] == sys.argv[1]:
		now = time()
                timediff = now - lasttime
		lasttime = now
                print("Device: {} Data: {} Time: {} Network: {} Timesince: {}".format(pydata['id'], pydata['data'][0], pydata['timestamp'], pydata['network'], timediff))
        else:
            print("Device: {} Data: {}".format(pydata['id'], pydata['data'][0]))
