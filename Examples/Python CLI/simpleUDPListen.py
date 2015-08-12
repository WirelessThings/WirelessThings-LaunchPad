#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast listener for Language of Things

    listen for UDP broadcasts on port 50140

"""
import sys
from time import time, sleep
import os
import socket

FROM_PORT = 50140
TO_PORT = 50141

sock = socket.socket(socket.AF_INET, # Internet
              socket.SOCK_DGRAM) # UDP

sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
if sys.platform == 'darwin':
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

sock.bind(('', FROM_PORT))

while True:
    data, addr = sock.recvfrom(1024)
    print("Got: {} from address {}".format(data, addr))
