#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast listener for LLAP

    listen for UDP broadcasts on port 50140

    """
import sys
import time
import os
import socket
import json

LLAP_FROM_PORT = 50140
LLAP_TO_PORT = 50141

def mysplit(s):
    head = s.rstrip("1234567890.-+")
    tail = s[len(head):]
    return head, tail

def log(s):
    #now = datetime.datetime.utcnow()
    #print(str(now) + "," + s)
    now = time.strftime("%Y/%m/%d %H:%M")
    f = open(time.strftime("%Y%m%d.log"),"a")
    print >>f,now + "," + str(time.time()/86400+25569) + "," + s
    f.close()

def log2(s,t):
    f = open(time.strftime("%Y%m%d.log",t),"a")
    print >>f,time.strftime("%Y/%m/%d %H:%M",t) + "," + str(time.mktime(t)/86400+25569) + "," + s
    f.close()
    #print(time.strftime("%Y/%m/%d %H:%M",t) +  "," + str(time.mktime(t)/86400+25569) + "," + s)

sock = socket.socket(socket.AF_INET, # Internet
              socket.SOCK_DGRAM) # UDP

sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
if sys.platform == 'darwin':
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

sock.bind(('', LLAP_FROM_PORT))

while True:
    data, addr = sock.recvfrom(1024)
#    print("Got: {} from address {}".format(data, addr))
    pydata=json.loads(data)
#    print("Py data: {}".format(pydata))
#    print("ID:{} LLAP:{}".format(pydata['id'],pydata['data']))
#    llapmsg = "a" + pydata['id'] + pydata['data'][0]
#    print(llapmsg)
    if pydata['type'] == 'LLAP' :
        timestamp = time.strptime(pydata['timestamp'],"%d %b %Y %H:%M:%S +0000")
        parts = mysplit(pydata['data'][0])
        log2(pydata['id'] + "," + parts[0] + "," + parts[1],timestamp)
