#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPConfigMeCore salve test module
    
Emulate the ConfigMe pair mode of a LLAP Therm module
"""
import sys, time, Queue, argparse, serial, threading

class ConfigMeSlave:
    """Slave tester for use against LLAPConfigMeCore test
        
    emulating the LLAP Thermistor firmware and commands needed for the testing
        
    """
    self.therm = {'HELL': ["HELLO", 5],
                  'CHDE': ["CHDEVID", 7],
                  'TMPA': ["TMPA20.00", 4],
                  'BVAL': ["BVAL3977", 4],
                  'INTV': ["INTVL000S", 5],
                  'DEVT': ["THERM00001", 7],
                  'CYCL': ["CYCLE", 5]
                  }

    def __intit__(self):
        self.confifMeID = "??"

        self.queue = Queue.Queue()
        self.transport = LLAPSerial.LLAPSerial(self.queue)

        parser = argparse.ArgumentParser(
                             description='LLAP ConfigMe Core logic test code')
        parser.add_argument('-p',
                            '--port',
                            help='Serial Port to Use for testing'
                            )
        parser.add_argument('-d', '--debug', help='Extra Debug Output',
                            action='store_true'
                            )
        
        args = parser.parse_args()

        if args.debug:
            self.debug = True
        else:
            self.debug = False

        self.transport = serial.Serial()
        self.transport.port = args.port
        self.transport.baud = 9600
        self.transport.timeout = 0.01       # 10 ms for startes

    def stop_pair(self):
        """exit pair mode early
        """
        self._pair = False
            
    def run(self):
        """blah
            
        open Serial
        a--STARTED
        go into ConfigMe mode 10 minutes
        send ConfigMe every 5 Sec, with 10ms listen for reply before sleeping
            
        stay awake if we get a message for ??, send ususaly reply, 
            wait another 10ms for another ?? message
            
        """
        self.transport.connect(self.port)
        self.transport.write("a{}STARTED--".formate(self.term[DEVID]))
        self._running = True

        self.cmTimeOut = Timer(600.0, self.transporttop_pair)
        self.cmTimeOut.start() # 10 minutes time out for ConfigMe mode
        
        while self._pair:
            try:
                self.loop()
            except KeyboardInterrupt:
                print("Keybord Quit")
                self._pair = False

    def loop(self):
        """ConfigMe loop
            
        """
        self.transport.flushInput()
        self.transport.write("a{}CONFIGME-".format(self.confifMeID))
        llapMsg = self.read_12()
        if llapMsg == "TIMEOUT":
            timm.sleep(5)
            # sleep for 5 sec
        else if llapMsg[1:3] == self.confifMeID:
            # decode llap and send correct reply
            if llapMsg[3:7] in self.therm:
                # we have a command we know
                
                # is it a get or set comand
                if llapMsg[3+self.therm[llapMsg[3:7][1]] == "-":
                    # get with a few special cases
                    if llapMsg == "a{}HELLO----".format(self.confifMeID):
                        llapReply = llapMsg
                    else if  llapMsg == "a{}CYCLE----".format(self.confifMeID):
                        llapReply = "{}a{}SLEEPING-".format(llapMsg, self.confifMeID)
                        self._pair = False
                    else:
                        llapReply = "a{}{}".format(self.confifMeID, self.therm[3+self.therm[llapMsg[3:7][0]]])
                        while len(llapReply) <12:
                           llapReply += '-'
                else:
                    # set
                    # get new value
                    value = llapMsg[3+self.therm[llapMsg[3:7][1]:]
                    print(value)
                    llapReply = llapMsg
                                    
                self.transport.write(llapReply)

    def read_12(self):
        """Read a llap message from transport
        
        Currently blocking
        """
       if self.transport.read() == 'a':
            llapMsg = 'a'
            llapMsg += self.transport.read(11)
            if self.debug:
                print("CMS: {}".format(llapMsg))
            return llapMsg
        return "TIMEOUT"




# tester code
if __name__ == "__main__":
    app = ConfigMeSlave
    app.run()