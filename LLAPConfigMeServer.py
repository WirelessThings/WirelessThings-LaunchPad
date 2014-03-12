#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPConfigMeServer module

Give a LLAPConfigReuest this will open the current transport and conducted
the requested exchanges returning a LLAPConfigReqesut complete with
replies to the calling application
"""
import sys
from time import time, sleep, gmtime, strftime
import os
import Queue
import argparse
import serial
import threading
import socket
import json

LLAP_FROM_PORT = 50140
LLAP_TO_PORT = 50141


class LLAPConfigRequest:
    """Config Request object
    
    Holder object for devType, Queries and replies
    
    toQuery is a ordered list commands to send, each as a dictionary of command, value
    Dicts are not ordered but lists are
    
    example dictionary
        {
         'command': "Command to send",
         'value': "this is optional value to send"
        }
        
    replies is a dict of commands and replies
        { command: {'reply': reply, 
                    'value': value}
        }
        { 'CHDEVID': {'replay': 'MA', 'value': "" }
    """
    def __init__(self, id, devType=None, toQuery=None, replies=None):
        self.id = id
        self.devType = devType
        self.toQuery = toQuery
        if replies == None:
            replies = {}
        self.replies = replies

    
class LLAPConfigMeCore(threading.Thread):
    """Core logic module
        
    Give a LLAPConfigRequest this will open the current transport and conducted
        the requested exchanges returning a LLAPConfigRequest complete with
        replies to the calling application
    """
    # serial based defaults
    _baud = 9600
    if sys.platform == 'darwin':
        #port = '/dev/tty.usbserial-B002'
        _serialPort = "/dev/tty.usbserial-A600L03S"
    elif sys.platform == 'win32':
        _serialPort = "COM1"
    else:
        _serialPort = "/dev/ttyAMA0"
    
    _LLAPSendPort = 50140   # we send stuff out on this port
    _LLAPListenPort = 50141     # we listen to this port

    _defaultNetwork = "Serial"
    
    debug = False
    keepAwake = False

    def __init__(self):
        """Instantiation
            
        Setup basic transport, Queue's, Threads etc
        """
        threading.Thread.__init__(self)

        self.disconnectFlag = threading.Event()
        self.t_stop = threading.Event()
        self.cancelFlag = threading.Event()
        
        self.replyQ = Queue.Queue()
        self.requestQ = Queue.Queue()
        self.transportQ = Queue.Queue()
        self._UDPSendQ = Queue.Queue()
        self._serialTXQ = Queue.Queue()
    
    def __del__(self):
        """Destructor
            
        Close any open threads, and transports
        """
        self.disconnect_transport()

    def _debugPrint(self, msg):
        if self.debug:
            print(msg)

    def set_port(self, port):
        """Set port for use by transport
        
        port
        """
        self._serialPort = port

    def set_baud(self, baud):
        """Set baud for use by transport
        
        """
        self._baud = baud

    def init_UDP(self):
        self._debugPrint("Init UDP")
        self._UDPSendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self._UDPSendT = threading.Thread(target=self._UDPSendThread)
        self._UDPSendT.setDaemon = True
        self._UDPSendT.start()

        self._UDPListenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._UDPListenSocket.bind(('', self._LLAPListenPort))

        self._UDPListenT = threading.Thread(target=self._UDPListenThread)
        self._UDPListenT.setDaemon(True)
        self._UDPListenT.start()

    def connect_transport(self):
        """Connect to the selected mode of transport and start the thread running
        """
        self.transport = serial.Serial()
        if self.transport.isOpen() == False:
            self.transport._baud = self._baud
            self.transport.timeout = 10       # for 10 second timeout reads
            self.transport.port = self._serialPort
            try:
                self.transport.open()
                self._debugPrint("LCMC: Transport open")
                self.start()
            except serial.SerialException, e:
                sys.stderr.write("LCMC: could not open port %r: %s\n" % (self._serialPort, e))
                sys.exit(1)
            # start the read thread
            return True
        else:
            return False
        
    def disconnect_transport(self):
        """Disconnect transport
        
        Will cause the thread to close on next loop
        """
        self.disconnectFlag.set()
            
    def run(self):
        """Run correct loop based on mode
        """
        self.runSerial()
    
    def runSerial(self):
        """Thread loop for processing serial input and actual items in a ConfigRequest
            
            
        """
        while self.transport.isOpen():
            if self.transport.inWaiting():
                char = self.transport.read()
                self.transportQ.put([char, "RX"])
                if self.cancelFlag.isSet():
                    self.cancelFlag.clear()
                    self.requestQ.get()
                    self.requestQ.task_done()
                if char == 'a':
                    llapMsg = 'a'
                    llapMsg += self.transport.read(11)
                    # TODO: Check we actuall got a whole packet (should not matter on LLAP master)
                    self.transportQ.put([llapMsg[1:], "RX"])
                    if llapMsg == "a??CONFIGME-":
                        # start of a CONFIGME cycle
                        # lets check the request queue
                        if not self.requestQ.empty():
                            request = self.requestQ.get()
                            # ok we got a request
                            self._debugPrint("LCMC: ID:{}, devType:{}, toQuery:{}".format(request.id,
                                                                                   request.devType,
                                                                                   request.toQuery))
                            # is it for a set devtype
                            if request.devType == None:
                                # process requests
                                request = self.processQuery(request)
                            
                            else:
                                # got a, need to check devtype first
                                llapReply = ""
                                llapMsg = "a??DTY------"
                            
                                # TODO: retry time out, should we recheck DTY?
                                while llapReply == "" or llapReply == "a??CONFIGME-":
                                    llapReply = ""  # clear last reply
                                    self.transport.write(llapMsg)
                                    self.transportQ.put([llapMsg, "TX"])
                                    
                                    # TODO: retry time out
                                    while llapReply[1:3] != "??" :
                                        llapReply = self.read_12()
                            
                                # don't need to pass DTY back up as it's not going to change
                                # request.replies.append([query,
                                #                        llapReply[3:].strip('-')])
                                
                                # check what DTY returned
                                if llapReply[6:].strip('-') == request.devType:
                                    request = self.processQuery(request)
                            
                            # TODO: check that we have replies for all queries's
                            if request != False:
                                self.replyQ.put(request)
                            self.requestQ.task_done()
                        elif self.keepAwake:
                            # nothing in the que but have been asked to keep device awake
                            # TODO: should we check we are keeping the correct device awake?
                            # although that in it's self will keep a deice awake
                            # could CONFIGEND if not the device been asked to keep awake
                            self._debugPrint("LCMC: Sending keepAwake HELLO")
                            llapReply = ""
                            llapMsg = "a??HELLO----"
                            while llapReply == "" or llapReply == "a??CONFIGME-":
                                self.transport.write(llapMsg)
                                self.transportQ.put([llapMsg, "TX"])
                                llapReply = ""
                                # TODO: retry time out
                                while llapReply[1:3] != "??" :
                                    llapReply = self.read_12()
                
                    else:
                        #not a CONFIGME llap
                        self._debugPrint("LCMC: Sending via UDP")
                        # encode to llap json and stick it on the outgoing udp queue
                        self._UDPSendQ.put(self.encodeLLAPJson(llapMsg))
        
            if not self._serialTXQ.empty():
                self._debugPrint("LCMC: Serial got something to send")
                # got something to send out
                llapMsg = self._serialTXQ.get()
                # TODO: is _serialTXQ pure LLAP?
                self.transport.write(llapMsg)
                self._debugPrint("LCMC: sent {} to serial".format(llapMsg))
                self._serialTXQ.task_done()

            if self.disconnectFlag.isSet():
                self.transport.close()
                self.disconnectFlag.clear()
            self.t_stop.wait(0.01)

    def read_12(self):
        """Read a llap message from transport
            
        Currently blocking
        """
        while self.transport.isOpen() == True:
            if self.transport.inWaiting():
                if self.transport.read() == 'a':
                    llapMsg = 'a'
                    eleven = self.transport.read(11)
                    if len(eleven) == 11:
                        # we didnt time out
                        llapMsg += eleven
                        self.transportQ.put([llapMsg, "RX"])
                        return llapMsg
                    else:
                        # so we got less that eleven
                        # what did we get?
                        # and can we get back in sync
                        pass

    def cancelLCR(self):
        self._debugPrint("LCMC: Got cancelLCR")
        self.cancelFlag.set()

    def processQuery(self, request):
        for query in request.toQuery:
            llapReply = ""
            llapMsg = "a??{}{}".format(query['command'], query.get('value', ""))
            while len(llapMsg) <12:
                llapMsg += '-'
            
            # TODO: retry time out, should we recheck DTY?
            while llapReply == "" or llapReply == "a??CONFIGME-":
                llapReply = ""  # clear last reply
                self.transport.write(llapMsg)
                self.transportQ.put([llapMsg, "TX"])
                
                # TODO: retry time out
                while llapReply[1:3] != "??" :
                    llapReply = self.read_12()
            
            if llapReply == llapMsg or llapReply[3:].strip('-').startswith(query['command']):
                request.replies[query['command']] = {'value': query.get('value', ""),
                                                     'reply': llapReply[3+len(query['command']):].strip('-')}
            else:
                # TODO: was it a reply to a different query?
                pass
            if self.cancelFlag.isSet():
                self.cancelFlag.clear()
                return False
        return request
                            
    def _UDPSendThread(self):
        """Thread handler for sending out UDP brodacasts
           Block on UDPSendQ untill something to send
        """
        self._debugPrint("LCMC: Running UDPSendThread")
        # TODO: should only run untill quit
        while 1:
            message = self._UDPSendQ.get()
            self._debugPrint(message)
            self._UDPSendSocket.sendto(message, ('<broadcast>', self._LLAPSendPort))
            self._debugPrint("LCMC: Put message out via UDP")
            # tidy up
            self._UDPSendQ.task_done()
    
    def _UDPListenThread(self):
        """Thread handler for sending out UDP brodacasts
           Block waiting fro incomming UDP packet
           
           """
        self._debugPrint("LCMC: Running UDPListenThread")
        # TODO: should only run untill quit
        while 1:
            data = self._UDPListenSocket.recv(1024)
            # TODO: decode incomming JSON and put LLAP messages on the Q
            jsonin = json.loads(data)
            
            if jsonin['type'] == "LLAP":
                # got a LLAP type json, need to generate the LLAP meassge and
                # put them on the TX que
                for command in jsonin['data']:
                    llapMsg = "a{}{}".format(jsonin['id'], command)
                    while len(llapMsg) <12:
                        llapMsg += '-'
                    
                    # send to each network requested
                    if jsonin['network'] == self._defaultNetwork or jsonin['network'] == "ALL":
                        # yep its for serial
                        self._serialTXQ.put(llapMsg)
                        self._debugPrint("LCMC: Put {} on serial.TXQ".format(llapMsg))
            elif jsonin['type'] == "LCR":
                # TODO: we have a LLAPConfigRequest pass in onto the LCR thread
                pass


    def encodeLLAPJson(self, message, network=None):
        """Encode a single LLAP message into an outgoing JSON message
        """
        self._debugPrint("LCMC: encodeing {} to json LLAP".format(message))
        jsonDict = {'type':"LLAP"}
        jsonDict['network'] = network if network else self._defaultNetwork
        jsonDict['timestamp'] = strftime("%d %b %Y %H:%M:%S +0000", gmtime())
        jsonDict['id'] = message[1:3]
        jsonDict['data'] = [message[3:].strip("-")]
        
        jsonout = json.dumps(jsonDict)
        self._debugPrint("LCMC: {}".format(jsonout))
        
        return jsonout
        
# tester code
if __name__ == "__main__" :
    """Class test code
        
    Prove that for a pre given config request the logic works
    """
    print("LLAP Server test code")
    t = threading.Event()
    parser = argparse.ArgumentParser(
                             description='LLAP ConfigMe Core logic test code')
  
    parser.add_argument('-p', '--port', help='Port to Use for testing')
    parser.add_argument('-d', '--debug', help='Extra Debug Output',
                        action='store_true'
                        )
    args = parser.parse_args()
    
    print("Init LCM object")
    lcm = LLAPConfigMeCore()
    
    if args.port:
        lcm.set_port(args.port)    # argphrase this???
    
    if args.debug:
        lcm.debug = True
    print("Argparse done")

    print("Init UDP")
    lcm.init_UDP()

    # build an example request, normally done via wizards
    query = [
             {'command': "DTY",
             },
             {'command': "LLAPRESET",
              'value': ""
             },
             {'command': "CHDEVID",
              'value': "MA"
             },
             {'command': "CONFIGEND",
             }
            ]
    lcr = LLAPConfigRequest(id=1, toQuery=query)

    print("Connecting transport")
    lcm.connect_transport()
    running = True
    t.wait(1)
    lcm.requestQ.put(lcr)
    try:
        while running:
            if not lcm.transportQ.empty():
                txt = lcm.transportQ.get()
                print("{} {}".format(txt[1], txt[0]))
                lcm.transportQ.task_done()
            if not lcm.replyQ.empty():
                reply = lcm.replyQ.get()
                print("id: {}, devType:{}, Replies:{}".format(reply.id,
                                                              reply.devType,
                                                              reply.replies))
                print("For DTY {} got:".format(reply.devType))
                for command, args in reply.replies.items():
                    print("Asked: {} with value: {} Got: {}".format(command,
                                                                    args['value'],
                                                                    args['reply']))
                lcm.replyQ.task_done()
                lcm.disconnect_transport()
                running = False
            t.wait(0.01)

    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        lcm.disconnect_transport()
        sleep(1)
        sys.exit()
        
