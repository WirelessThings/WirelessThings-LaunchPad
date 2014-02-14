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
    _mode = SERIAL
    _baud = 9600
    if sys.platform == 'darwin':
        #port = '/dev/tty.usbserial-B002'
        _serialPort = "/dev/tty.usbserial-A600L03S"
    elif sys.platform == 'win32':
        _serialPort = "COM1"
    else:
        _serialPort = "/dev/ttyAMA0"
    
    # mqtt defaults
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
        self._mqttQ = Queue.Queue()
    
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
                self._mqttPort = 1883    # default port for mqtt if not given
    
    def set_baud(self, baud):
        """Set baud for use by transport
        
        """
        if self._mode == SERIAL:
            self._baud = baud
    
    def connect_transport(self):
        """Connect to the selected mode of transport and start the thread running
        """
        if self._mode == SERIAL:
            self.transport = serial.Serial()
            if self.transport.isOpen() == False:
                self.transport._baud = self._baud
                self.transport.timeout = 10       # for 10 second timeout reads
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
            """MQTT based transport using mosquitto
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
        """Disconnect transport
        
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
        while not self.disconnectFlag.isSet():
            if not self._mqttQ.empty():
                msg = self._mqttQ.get()
                if msg.payload == "CONFIGME":
                    # start of a CONFIGME Cycle
                    # lets check the request queue
                    if not self.requestQ.empty():
                        request = self.requestQ.get()
                        # ok we got a request
                        if self.debug:
                            print("LCMC: ID:{}, devType:{}, toQuery:{}".format(request.id,
                                                                               request.devType,
                                                                               request.toQuery))
                        # is it for a set devtype
                        if request.devType == None:
                            # process requests
                            for query in request.toQuery:
                                self.transport.publish(self._mqttPub_tx, query)
                                self.transportQ.put(["{}:{}".format(self._mqttPub_tx,
                                                                    query), "TX"])
                                
                                while self._mqttQ.empty():
                                    self.t_stop.wait(0.01)
                                
                                reply = self._mqttQ.get()
                                request.replies.append([query, reply.payload])
                                self._mqttQ.task_done()
                        
                        else:
                            # got a need to check devtype first
                            query = {'command': "DTY"}
                            self.transport.publish(self._mqttPub_tx, query)
                            self.transportQ.put(["{}:{}".format(self._mqttPub_tx,
                                                                query), "TX"])
                            
                            while self._mqttQ.empty():
                                self.t_stop.wait(0.01)
                                    
                            reply = self._mqttQ.get()
                            request.replies.append([query, reply.payload])
                            self._mqttQ.task_done()
                            
                            if reply.payload == request.devType:
                                # got a matching devtype, time to send all the requests
                                for query in request.toQuery:
                                    self.transport.publish(self._mqttPub_tx, query)
                                    self.transportQ.put(["{}:{}".format(self._mqttPub_tx,
                                                                        query), "TX"])
                                                                        
                                    while self._mqttQ.empty():
                                        self.t_stop.wait(0.01)
                                    
                                    reply = self._mqttQ.get()
                                    request.replies.append([query, reply.payload])
                                    self._mqttQ.task_done()
                        
                        self.replyQ.put(request)
                        self.requestQ.task_done()
                    elif self.keepAwake:
                        # nothing in the que but have been asked to keep device awake
                        if self.debug:
                            print("LCMC: Sending keepAwake HELLO")
                        llapMsg = "a??HELLO----"
                        self.transport.publish(self._mqttPub_tx, "HELLO")
                        self.transportQ.put(["{}:HELLO".format(self._mqttPub_tx), "TX"])
                        while self._mqttQ.empty():
                            self.t_stop.wait(0.01)
                                
                        reply = self._mqttQ.get()
                        self._mqttQ.task_done()
                else:
                    #not a CONFIGME llap
                    pass

                self._mqttQ.task_done()
            self.t_stop.wait(0.01)
        self.transport.disconnect()
    
    def mqttOnMessage(self, mosq, obj, msg):
        """Received Message from MQTT
        """
        if self.debug:
            print("LCMC: Received on topic {} with QoS {}  and payload {}".format(msg.topic,
                                                                                  msg.qos,
                                                                                  msg.payload))
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
                                print("LCMC: ID:{}, devType:{}, toQuery:{}".format(request.id,
                                                                                   request.devType,
                                                                                   request.toQuery))
                            # is it for a set devtype
                            if request.devType == None:
                                # process requests
                                request = self.processQuery(request)
                            
                            else:
                                # got a need to check devtype first
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
                            self.replyQ.put(request)
                            self.requestQ.task_done()
                        elif self.keepAwake:
                            # nothing in the que but have been asked to keep device awake
                            # TODO: should we check we are keeping the correct device awake?
                            # although that in it's self will keep a deice awake
                            # could CONFIGEND if not the device been asked to keep awake
                            if self.debug:
                                print("LCMC: Sending keepAwake HELLO")
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
                request.replies[query['command']] = {'value': query.get('value', ""), 'reply': llapReply[3+len(query['command']):].strip('-')}
            else:
                # TODO: was it a reply to a different query?
                pass
        return request
                            

# tester code
if __name__ == "__main__" :
    """Class test code
        
    Prove that for a pre given config request the logic works
    """
    t = threading.Event()
    parser = argparse.ArgumentParser(
                             description='LLAP ConfigMe Core logic test code')
    parser.add_argument('-m', '--mqtt', help='Use MQTT for transport',
                        action='store_true'
                        )
    parser.add_argument('-p', '--port', help='Port to Use for testing')
    parser.add_argument('-d', '--debug', help='Extra Debug Output',
                        action='store_true'
                        )
    
    args = parser.parse_args()
    
    lcm = LLAPConfigMeCore()
    
    if args.mqtt:
        lcm.set_mode(MQTT)
    
    if args.port:
        lcm.set_port(args.port)    # argphrase this???
    
    if args.debug:
        lcm.debug = True
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
                    print("Asked: {} with value: {} Got: {}".format(command, args['value'], args['reply']))
                lcm.replyQ.task_done()
                lcm.disconnect_transport()
                running = False
            t.wait(0.01)

    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        lcm.disconnect_transport()
        sleep(1)
        sys.exit()
        
