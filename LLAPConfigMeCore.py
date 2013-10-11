#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPConfigMeCore logic module

Give a LLAPConfigReuest this will open the current transport and conducted
the requested exchanges returning a LLAPConfigReqesut complete with
replies to the calling application
"""
import sys
import time as time_
import Queue
import argparse
import serial
import threading



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
    
    def __init__(self):
        """Instantiation
            
        Setup basic transport, Queue's, Threads etc
        """
        threading.Thread.__init__(self)
        
        self.baud = 9600
        self.port = "/dev/ttyAMA0" # could be IP for UDP layer
        self.debug = False

        self.t_stop = threading.Event()
        
        self.replyQ = Queue.Queue()
        self.requestQ = Queue.Queue()
        self.transportQ = Queue.Queue()
        
        #setup transport bits
        self.transport = serial.Serial()
    
    def __del__(self):
        """Destructor
            
        Close any open threads, and transports
        """
        self.disconnect_transport()
    
    def set_port(self, port):
        """Set port for use by transport
            
        determine transport based on port type
        setup serial connection basics ??
        """
        self.port = port
    
    def set_baud(self, baud):
        """Set buad for use by transport
        
        """
        self.baud = baud
    
    def connect_transport(self):
        if self.transport.isOpen() == False:
            self.transport.baud = self.baud
            self.transport.timeout = 45       # for 45 second timeout reads
            self.transport.port = self.port
            try:
                self.transport.open()
                if self.debug:
                    print("LCMC: Transport open")
                self.start()
            except serial.SerialException, e:
                sys.stderr.write("LCMC: could not open port %r: %s\n" % (self.port, e))
                sys.exit(1)
            # start the read thread
            return True
        else:
            return False

    def disconnect_transport(self):
        """Disconnet transport
        
        should be no running thread using the open connection
        """
        if self.transport.isOpen() == True:
            if self.debug:
                print("LCMC: Disconnecting Transport")
            self.transport.close()
            
    def run(self):
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
                        # ets check the reuest queue
                        if not self.requestQ.empty():
                            request = self.requestQ.get()
                            # ok we got a request
                            if self.debug:
                                print("LCMC: ID: {} devType: {} Query commnads {}".format(request.id, request.devType, request.toQuery))
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
                                    
                                    request.replies.append([llapMsg[3:].strip('-'),llapReply[3:].strip('-')])
                        
                            else:
                                # got a need to check devtype first
                                llapMsg = "a??DEVTYEP--"
                                self.transport.write(llapMsg)
                                self.transportQ.put([llapMsg, "TX"])

                                llapReply = ""
                                while llapReply[1:3] != "??" :
                                    llapReply = self.read_12()
                                
                                request.replies.append([llapMsg[3:].strip('-'),llapReply[3:].strip('-')])
                                
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
                                        
                                        request.replies.append([llapMsg[3:].strip('-'),llapReply[3:].strip('-')])
                
                            self.replyQ.put(request)
                            self.requestQ.task_done()
                    else:
                        #not a CONFIGME llap
                        pass
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
    parser.add_argument('-p', '--port', help='Serial Port to Use for testing')
    parser.add_argument('-d', '--debug', help='Extra Debug Output',
                        action='store_true'
                        )
    
    args = parser.parse_args()
    
    lcm = LLAPConfigMeCore()
    
    if args.port:
        lcm.set_port(args.port)    # argphrase this???
    
    if args.debug:
        lcm.debug = True
    # build an example request, normall done via wizzards
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
                    print("Asked {} got {}".format(reply.replies[n][0], reply.replies[n][1]))
                lcm.replyQ.task_done()
                lcm.disconnect_transport()
                running = False
            t.wait(0.01)

    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        lcm.disconnect_transport()
        sys.exit()
        



