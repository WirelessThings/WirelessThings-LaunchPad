#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPConfigMeCore logic module

Give a LLAPConfigReuest this will open the current transport and conducted
the requested exchanges returning a LLAPConfigReqesut complete with
replies to the calling application
"""
import sys
from time import time, sleep
import os
import Queue
import argparse
import serial
import threading
import mosquitto

SERIAL = 'serial'
MQTT = 'mqtt'

class LLAPConfigRequest:
    """Config Request object
    
    Holder object for devType, Queries and replies
    """
    def __init__(self, id, devType=None, toQuery=None, replies=None):
        self.id = id
        self.devType = devType
        self.toQuery = toQuery
        if replies == None:
            replies = []
        self.replies = replies

    
class LLAPConfigMeCore(threading.Thread):
    """Core logic module
        
    Give a LLAPConfigReuest this will open the current transport and conducted 
        the requested exchanges returning a LLAPConfigReqesut complete with 
        replies to the calling application
    """
    # serial based defualts
    _mode = SERIAL
    _baud = 9600
    _serialPort = "/dev/ttyAMA0"
    
    # mqtt defualts
    clientName = "LLAPConfigmeCore"
    _mqttServer = 'localhost'
    _mqttPort = 1883
    _mqttSub_rx = 'llap/rx/??'
    #_mqttSub_rx_mask = 'llap/rx/'
    _mqttPub_tx = 'llap/tx/??'
    
    debug = False
    keepAwake = False

    def __init__(self):
        """Instantiation
            
        Setup basic transport, Queue's, Threads etc
        """
        threading.Thread.__init__(self)

        self.disconnectFlag = threading.Event()
        self.t_stop = threading.Event()
        
        self.replyQ = Queue.Queue()
        self.requestQ = Queue.Queue()
        self.transportQ = Queue.Queue()
    
    def __del__(self):
        """Destructor
            
        Close any open threads, and transports
        """
        self.disconnect_transport()
    
    def set_mode(self, mode):
        """Set the transport mode
            
        mode SERIAL or MQTT
        """
        self._mode = mode
    
    def set_port(self, port):
        """Set port for use by transport
        
        port
        """
        if self._mode == SERIAL:
            self._serialPort = port
        elif self._mode == MQTT:
            port = port.split(':')
            self._mqttServer = port[0]
            if len(port) == 2:
                self._mqttPort = port[1]
            else:
                self._mqttPort = 1833    # defualt port for mqtt if not given
    
    def set_baud(self, baud):
        """Set buad for use by transport
        
        """
        if self._mode == SERIAL:
            self._baud = baud
    
    def connect_transport(self):
        """Connet to the selected mode of tansport and start the thread running
        """
        if self._mode == SERIAL:
            self.transport = serial.Serial()
            if self.transport.isOpen() == False:
                self.transport._baud = self._baud
                self.transport.timeout = 45       # for 45 second timeout reads
                self.transport.port = self._serialPort
                try:
                    self.transport.open()
                    if self.debug:
                        print("LCMC: Transport open")
                    self.start()
                except serial.SerialException, e:
                    sys.stderr.write("LCMC: could not open port %r: %s\n" % (self._serialPort, e))
                    sys.exit(1)
                # start the read thread
                return True
            else:
                return False
        elif self._mode == MQTT:
            """MQTT based trasnport using mosquitto
            """
            self.transport = mosquitto.Mosquitto(self.clientName)
            self.transport.on_message = self.mqttOnMessage
            self.transport.connect(host=self._mqttServer, port=self._mqttPort)
            self.transport.loop_start()
            self.transport.subscribe(self._mqttSub_rx)
            if self.debug:
                print("LCMC: Transport open")
            self.start()
            return True

    def disconnect_transport(self):
        """Disconnet transport
        
        Will cause the thread to close on next loop
        """
        self.disconnectFlag.set()
            
    def run(self):
        """Run correct loop based on mode
        """
        if self._mode == SERIAL:
            self.runSerial()
        elif self._mode == MQTT:
            self.runMqtt()

    def runMqtt(self):
        """MQTT based run loop
        """
        pass
    def mqttOnMessage(self, mosq, obj, msg):
        """Recieved Message from MQTT
        """
        if self.debug:
            print("LCMC: Received on topic {} with QoS {}  and payload {}".format(msg.topic, msg.qos, msg.payload))
        self.transportQ.put(["{}:{}".format(msg.topic, msg.payload), "RX"])
        self._mqttQ.put(msg)
    
    def runSerial(self):
        """Thread loop for processing serial input and actual items in a ConfigRequest
            
            
        """
        while self.transport.isOpen():
            if self.transport.inWaiting():
                char = self.transport.read()
                self.transportQ.put([char, "RX"])
                if char == 'a':
                    llapMsg = 'a'
                    llapMsg += self.transport.read(11)
                    self.transportQ.put([llapMsg[1:], "RX"])
                    if llapMsg == "a??CONFIGME-":
                        # start of a CONFIGME cycle
                        # lets check the request queue
                        if not self.requestQ.empty():
                            request = self.requestQ.get()
                            # ok we got a request
                            if self.debug:
                                print("LCMC: ID:{}, devType:{}, toQuery:{}".format(request.id, request.devType, request.toQuery))
                            # is it for a set devtype
                            if request.devType == None:
                                # procces reuests
                                for query in request.toQuery:
                                    llapMsg = "a??{}".format(query)
                                    while len(llapMsg) <12:
                                        llapMsg += '-'
                                    
                                    self.transport.write(llapMsg)
                                    self.transportQ.put([llapMsg, "TX"])
                                    
                                    llapReply = ""
                                    while llapReply[1:3] != "??" :
                                        llapReply = self.read_12()
                                    
                                    request.replies.append([llapMsg[3:].strip('-'),
                                                            llapReply[3:].strip('-')])
                        
                            else:
                                # got a need to check devtype first
                                llapMsg = "a??DEVTYPE--"
                                self.transport.write(llapMsg)
                                self.transportQ.put([llapMsg, "TX"])

                                llapReply = ""
                                while llapReply[1:3] != "??" :
                                    llapReply = self.read_12()
                                
                                request.replies.append([llapMsg[3:].strip('-'),
                                                        llapReply[3:].strip('-')])
                                
                                if llapReply[3:].strip('-') == request.devType:
                                    # got a matching devtype, time to send all the requests
                                    for query in request.toQuery:
                                        llapMsg = "a??{}".format(query)
                                        while len(llapMsg) <12:
                                            llapMsg += '-'
                                        
                                        self.transport.write(llapMsg)
                                        self.transportQ.put([llapMsg, "TX"])

                                        llapReply = ""
                                        while llapReply[1:3] != "??" :
                                            llapReply = self.read_12()
                                        
                                        request.replies.append([llapMsg[3:].strip('-'),
                                                                llapReply[3:].strip('-')])
                
                            self.replyQ.put(request)
                            self.requestQ.task_done()
                        elif self.keepAwake:
                            # nothing in the que but have been asked to keep device awake
                            if self.debug:
                                print("LCMC: Sending keepAwake HELLO")
                            llapMsg = "a??HELLO----"
                            self.transport.write(llapMsg)
                            self.transportQ.put([llapMsg, "TX"])
                            llapReply = ""
                            while llapReply[1:] != "??HELLO----" :
                                llapReply = self.read_12()
                
                    else:
                        #not a CONFIGME llap
                        pass
            if self.disconnectFlag.isSet():
                self.transport.close()
                self.disconnectFlag.clear()
            self.t_stop.wait(0.01)

    def read_12(self):
        """Read a llap message from transport
            
        Currently blocking
        """
        while self.transport.isOpen() == True:
            if self.transport.inWaiting() >= 12:
                if self.transport.read() == 'a':
                    llapMsg = 'a'
                    llapMsg += self.transport.read(11)
                    self.transportQ.put([llapMsg, "RX"])
                    return llapMsg



# tester code
if __name__ == "__main__" :
    """Class test code
        
    Prove that for a pre given confifg request the logic works
    """
    t = threading.Event()
    parser = argparse.ArgumentParser(
                             description='LLAP ConfigMe Core logic test code')
    parser.add_argument('-p', '--port', help='Port to Use for testing')
    parser.add_argument('-d', '--debug', help='Extra Debug Output',
                        action='store_true'
                        )
    
    args = parser.parse_args()
    
    lcm = LLAPConfigMeCore()
    
    if args.port:
        lcm.set_port(args.port)    # argphrase this???
    
    if args.debug:
        lcm.debug = True
    # build an example request, normall done via wizards
    query = ["CHDEVIDAA", "INTVL005M", "CYCLE"]
    lcr = LLAPConfigRequest(id=1, devType="THERM001", toQuery=query)

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
                print("For DEVTYPE {} got:".format(reply.devType))
                for n in range(len(reply.replies)):
                    print("Asked {} got {}".format(reply.replies[n][0],
                                                   reply.replies[n][1]))
                lcm.replyQ.task_done()
                lcm.disconnect_transport()
                running = False
            t.wait(0.01)

    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        lcm.disconnect_transport()
        sleep(1)
        sys.exit()
        



