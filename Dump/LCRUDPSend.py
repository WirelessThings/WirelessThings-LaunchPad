#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple UDP broadcast sender for LLAP
    
    Send LLAP Json via UDP broadcasts on port 50141
    
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

jsonDict = {'type':"LCR"}
jsonDict['network'] = "ALL"      # could be 'Serial' or 'ALL'

jsonDict['data'] = {
                    "id":0,
                    "keepAwake":0,
                    "devType":"THERM2",
                    "timeout":300,
                    "toQuery":[{
                        "command":"APVER"
                        },
                        {
                        "command":"DTY"
                        },
                        {
                        "command":"CHDEVID"
                        }]
                    }

jsonout = json.dumps(jsonDict)

sock.sendto(jsonout, ('<broadcast>', LLAP_TO_PORT))
