#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPConfigMeCore logic module

Give a LLAPConfigReuest this will open the current transport and conducted
the requested exchanges returning a LLAPConfigReqesut complete with
replies to the calling application
"""
import sys, time, Queue, argparse, serial, threading


class LLAPConfigRequest:
    """Config Request object
    
    Holder object for devType, Queries and replies
    """
    def __init__(self, devType, toQuery=None, replies=None):
        self.devType = devType
        self.toQuery = toQuery
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
        
        self.devid = "PI"
        self.port = "/dev/ttyAMA0" # could be IP for UDP layer
        self.debug = False

        self.daemon = True

        self.t_stop = threading.Event()
        
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
    
    
    def connect_transport(self):
        if self.transport.isOpen() == False:
            self.transport.baud = 9600
            self.transport.timeout = 45       # for 45 second timeout reads
            self.transport.port = self.port
            try:
                self.transport.open()
                self.transport.write("a{}STARTED--".format(self.devid))
                if self.debug:
                    print("LCMC: Transport open")
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


    def process_request(self, request, replyQueue):
        """Process a ConfigRequest 
            
            
            try open port
            try connect
            start thread,
        """
        self.request = request
        self.replyQueue = replyQueue
        if self.connect_transport():
            if self.debug:
                print("LCMC: Starting worker thread")
            self.start()
            return True
        else:
            return False
            
    def run(self):
        """Thread loop for processing actual items in a ConfigRequest
            
            
        we have a config request and open serial port
        check devtype first
        start 45sec timeout
        so empty buffer
        wait for 12
            look for ?? configme
            send devtype
            wait for 12 reply
            if matches carry on
            else fail,
                return devtype in replies only
            
            for each request:
                send request
                wait for 12
                    if confifMe
                        missed window resend
        
                got reply?
                    file it
                not for us, next 12?
            
            got replies
            return via queue
            stop
        
        """
        if self.debug:
            print("LCMC: Thread Started")
        self.transport.flushInput()
        llapMsg = ""
        while llapMsg != "a??CONFIGME-":
            llapMsg = self.read_12()
        
        if self.debug:
                print("LCMC: Got a??CONFIGME-")
        self.transport.write("a??DEVTYEP--")
        llapMsg = ""
        while llapMsg[1:3] != "??" :
            llapMsg = self.read_12()

        if self.debug:
            print("LCMC: Sent DevType Reuest got {}".format(llapMsg[3:]))

        if llapMsg[3:] == "CONFIGME-":
            # missed it send again
            self.transport.flushInput()
            self.transport.write("a??DEVTYEP--")
            llapMsg = ""
            while llapMsg[1:3] != "??" :
                llapMsg = self.read_12()

        self.request.replies = [llapMsg[3:]]
        
        if llapMsg[3:] == self.request.devType:
            # got got a matching devtype, time to send all the requests
            if self.debug:
                print("LCMC: Got matching DevType")
            for query in self.request.toQuery:
                llapMsg = "a??{}".format(query)
                while len(llapMsg) <12:
                    llapMsg += '-'
                
                self.transport.write(llapMsg)

                llapMsg = ""
                while llapMsg[1:3] != "??" :
                    llapMsg = self.read_12()
                
                self.request.replies.append(llapMsg[3:])
                if self.debug:
                    print("LCMC: Got {} in reply to {}".format(llapMsg[3:],
                                                               query
                                                               )
                          )
    

        self.replyQueue.put(self.request)
        if self.debug:
            print("LCMC: put replies on the Queue")
        self.disconnect_transport()



    def read_12(self):
        """Read a llap message from transport
            
        Currently blocking
        """
        while self.transport.isOpen() == True:
            if self.transport.inWaiting() >= 12:
                if self.transport.read() == 'a':
                    llapMsg = 'a'
                    llapMsg += self.transport.read(11)
                    if self.debug:
                        print("LCMC: {}".format(llapMsg))
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
    
    retQueue = Queue.Queue()
    lcm = LLAPConfigMeCore()
    
    if args.port:
        lcm.set_port(args.port)    # argphrase this???
    
    if args.debug:
        lcm.debug = True
    # build an example request, normall done via wizzards
    query = ["CHDEVIDAA", "INTVL005M", "CYCLE"]
    lcr = LLAPConfigRequest("THERM0001", toQuery=query)

    try:
        lcm.process_request(lcr, retQueue)

        # wait item in queue
        while retQueue.empty():
            t.wait(0.01)

        reply = retQueue.get()
        for r in reply.replies:
            print(r)
    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        sys.exit()
        



