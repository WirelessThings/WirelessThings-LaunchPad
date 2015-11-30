#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Device reset helper

    Simple script to help reset a device back to factory settings

    usage
    $ python DCRDeviceReset.py -- HELLO
    or
    $ ./DCRDeviceReset.py MA TEMP

    Optionally you can speficy a network via an argument
    Other wise the request will be send to "Serial" network

    $ ./DCRDeviceReset.py Serial


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
try:
    sock.sendto(jsonout, ('<broadcast>', TO_PORT))
except socket.error as msg:
    if msg[0] == 101:
        try:
            sock.sendto(jsonout, ('127.0.0..255', TO_PORT))
        except socket.error as msg:
            print("Failed to send, Error code : {} Message: {}".format(msg[0], msg[1]))
        else:
            print("Sent: {}".format(jsonout))
    else:
        print("Failed to send, Error code : {} Message: {}".format(msg[0], msg[1]))
else:
    print("Sent: {}".format(jsonout))

sock.close()
