#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Device reset helper

    Simple script to help reset a device back to factory settings

    Uasge
    $ python DCRDeviceReset.py -- HELLO
    or
    $ ./DCRDeviceReset.py MA TEMP

    Optionally you can speficy a network via an argument
    Other wise the request will be send to "Serial" network

    $ ./DCRDeviceReset.py Serial

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

jsonDict = {'type':"DeviceConfigurationRequest"}

if len(sys.argv) == 2:
    jsonDict['network'] = sys.argv[1]
else:
    jsonDict['network'] = "Serial"      # could be 'Serial' or 'ALL'

jsonDict['data'] = {
                    "id":0,
                    "keepAwake":0,
                    "timeout":60,
                    "toQuery":[{
                        "command":"APVER"
                        },
                        {
                        "command":"LLAPRESET"
                        },
                        {
                        "command":"REBOOT"
                        }]
                    }

jsonout = json.dumps(jsonDict)

sock.sendto(jsonout, ('<broadcast>', TO_PORT))
print("Sent: {}".format(jsonout))
sock.close()
