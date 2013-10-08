#!/usr/bin/env python

# Ciseco Python LLAPSerial transport layer

import serial, threading, Queue, time, sys


class LLAPSerial:
    
    def __init__(self, queue=None):
        self.queue = queue
        self.s = serial.Serial()
        self.s.baudrate = 9600
        self.s.timeout = 0            # non-blocking read's
        self.t_stop= threading.Event()
        self.t = serialReadThread(self.queue, self.s, self.t_stop)
    
    # class deinitialization
    def __del__(self):
        self.disconnect()
    
    def connect(self, port):
        if self.s.isOpen() == False:
            self.s.port = port
            try:
                self.s.open()
            except serial.SerialException, e:
                sys.stderr.write("could not open port %r: %s\n" % (port, e))
                sys.exit(1)
            # start the read thread
            self.t.start()
            return True
        else:
            return False

    def disconnect(self):
        # closeing the serial port will stop the thread
        if self.s.isOpen() == True:
            self.t_stop.set()
            self.s.close()

    
    def sendLLAP(self, devID, data):
        llapMsg = "a{}{}".format(devID, data)
        while len(llapMsg) < 12:
            llapMsg += '-'
        if self.s.isOpen() == True:
            self.s.write(llapMsg)

class serialReadThread(threading.Thread):
    def __init__(self, queue, serial, t_stop):
        threading.Thread.__init__(self)
        self.queue = queue
        self.s = serial
        self.t_stop = t_stop
    
    def run(self):
        while self.s.isOpen() == True:
            if self.s.inWaiting() >= 12:
                if self.s.read() == 'a':
                    llapMsg = 'a'
                    llapMsg += self.s.read(11)
                    self.queue.put({'devID': llapMsg[1:3], 'payload': llapMsg[3:].rstrip("-")})
            self.t_stop.wait(0.01)

# tester code
if __name__ == "__main__":
    q = Queue.Queue()
    l = LLAPSerial(q)
    if l.connect('/dev/ttyAMA0'):
        print("Connected, Entering Loop")
        l.sendLLAP("--","STARTED")
        while True:
            lmsg = q.get()
            print(lmsg)
            time.sleep(0.5)



