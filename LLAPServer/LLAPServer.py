#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPServer


"""
import sys
from time import time, sleep, gmtime, strftime
import os
import Queue
import argparse
import ConfigParser
import serial
import threading
import socket
import json
import logging

"""
   Big TODO list
   
   LCR logic
   
   better serial read logic
   
   Catch Ctrl-C
   Clean up on quit code
   Clean up on die code
   
   Thread state monitor
   gpio state display
   restart dead threads
   restart dead serial
   restart dead socket
   
   "SERVER" messages
        status
        reboot
        stop
        config change
        
   configure llap master command line option
   
   
"""

class LLAPServer(threading.Thread):
    """Core logic and master thread control
        
    LLAPServer looks after the following threads
    Serial
    LCR
    UDP Send
    UDP Listen
    
    It starts by loading the LLAPServerConfig.cfg file
    Seting up debug out put and logging
    Then starts the threads for the various transport layers
    
    
    """
    _LCRKeepAwake = False
    
    _configFile = "./LLAPServer.cfg"
    _configFileDefault = "./LLAPServerDefault.cfg"
    
    _serialTimeout = 10     # serial port time out setting
    
    _version = 0.01
    
    def __init__(self, logger=None):
        """Instantiation
            
        Setup basic transport, Queue's, Threads etc
        """
        threading.Thread.__init__(self)
        
        self.tMainStop = threading.Event()
        
        # setup initial Loging
        logging.getLogger().setLevel(logging.NOTSET)
        self.logger = logging.getLogger('LLAPServer')
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.WARN)    # this should be WARN by defualt
        self._formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._ch.setFormatter(self._formatter)
        self.logger.addHandler(self._ch)
    
    def __del__(self):
        """Destructor
            
        Close any open threads, and transports
        """
        # TODO: shut down anything we missed
        pass

    def run(self):
        """Start doing everthing running
           This is the main entry point
        """
        self.logger.info("Start")
        try:
            self._checkArgs()           # pull in the command line options
            self._readConfig()          # read in the config file
            self._initLogging()         # setup the logging options
            self._initLCRThread()       # start the LLAPConfigRequest thread
            self._initUDPSendThread()   # start the UDP sender
            self.tMainStop.wait(1)
            self._initSerialThread()    # start the serial port thread
            self.tMainStop.wait(1)
            self._initUDPListenThread() # start the UDP listener
            
            # TODO: main loop
            while 1:
                #self.logger.debug(" main loop")
                self.tMainStop.wait(1)
            
        except KeyboardInterrupt:
            self.logger.info("Keyboard Interrupt")
            sys.exit(1)

    def _checkArgs(self):
        """Parse the command line options
        """
        parser = argparse.ArgumentParser(description='LLAP Server')
        parser.add_argument('-u', '--noupdate',
                            help='disable checking for update',
                            action='store_false')
        parser.add_argument('-d', '--debug',
                            help='Enable debug output to console, overrides wik.cfg setting',
                            action='store_true')
        parser.add_argument('-l', '--log',
                            help='Override the debug logging level, DEBUG, INFO, WARNING, ERROR, CRITICAL'
                            )
                            
        self.args = parser.parse_args()

    def _readConfig(self):
        """Read the server config file from disk
        """
        self.logger.info("Reading config files")
        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self._configFileDefault))
        except:
            self.logger.error("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self._configFile):
            self.logger.error("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self.logger.critical("No Config Loaded, Quitting")
            self.die()
    
    def writeConfig(self):
        self.logger.info("Writing config file")
        with open(self._configFile, 'wb') as configfile:
            self.config.write(configfile)
    
    def _initLogging(self):
        """ now we have the config file loaded and the command line args setup
            setup the loggers
        """
        self.logger.info("Setting up Loggers. Console output may stop here")

        # disable logging if no optinos are enabled
        if (self.args.debug == False and
            self.config.getboolean('Debug', 'console_debug') == False and
            self.config.getboolean('Debug', 'file_debug') == False):
            self.logger.debug("Disabling loggers")
            # disable debug output
            self.logger.setLevel(100)
            return
        # set console level
        if (self.args.debug or self.config.getboolean('Debug', 'console_debug')):
            self.logger.debug("Setting Console debug level")
            if (self.args.log):
                logLevel = self.args.log
            else:
                logLevel = self.config.get('Debug', 'console_level')
        
            numeric_level = getattr(logging, logLevel.upper(), None)
            if not isinstance(numeric_level, int):
                raise ValueError('Invalid console log level: %s' % loglevel)
            self._ch.setLevel(numeric_level)
        else:
            self._ch.setLevel(100)

        # add file logging if enabled
        # TODO: look at rotating log files
        # http://docs.python.org/2/library/logging.handlers.html#logging.handlers.TimedRotatingFileHandler
        if (self.config.getboolean('Debug', 'file_debug')):
            self.logger.debug("Setting file debuger")
            self._fh = logging.FileHandler(self.config.get('Debug', 'log_file'))
            self._fh.setFormatter(self._formatter)
            logLevel = self.config.get('Debug', 'file_level')
            numeric_level = getattr(logging, logLevel.upper(), None)
            if not isinstance(numeric_level, int):
                raise ValueError('Invalid console log level: %s' % loglevel)
            self._fh.setLevel(numeric_level)
            self.logger.addHandler(self._fh)
            self.logger.info("File Logging started")
                
    def _initLCRThread(self):
        """ Setup the Thread and Queues for handleing LLAPConfigRequests
        """
        self.logger.info("LCR Thread init")

        self.qLCRRequest = Queue.Queue()
        self.qLCRSerial = Queue.Queue()
        
        self.tLCRStop = threading.Event()

        self.tLCR = threading.Thread(target=self._LCRThread)
        self.tLCR.daemon = False

        try:
            self.tLCR.start()
        except:
            self.logger.exception("Failed to Start the LCR thread")
            
    def _initUDPSendThread(self):
        """ Start the UDP output thread
        """
        self.logger.info("UDP Send Thread init")
    
        self.qUDPSend = Queue.Queue()
        
        self.tUDPSendStop = threading.Event()
    
        self.tUDPSend = threading.Thread(target=self._UDPSendTread)
        self.tUDPSend.daemon = False

        try:
            self.tUDPSend.start()
        except:
            self.logger.exception("Failed to Start the UDP send thread")

    def _initSerialThread(self):
        """ Setup the serial port and start the thread
        """
        self.logger.info("Serial port init")

        # serial port base on config file, thread handels opening and closeing
        self._serial = serial.Serial()
        self._serial.port = self.config.get('Serial', 'port')
        self._serial.baud = self.config.get('Serial', 'baudrate')
        self._serial.timeout = self._serialTimeout
        
        # setup queue
        self.qSerialOut = Queue.Queue()
        
        # setup thread
        self.tSerialStop = threading.Event()
    
        self.tSerial = threading.Thread(target=self._SerialThread)
        self.tSerial.daemon = False
    
        try:
            self.tSerial.start()
        except:
            self.logger.exception("Failed to Start the Serial thread")

    def _initUDPListenThread(self):
        """ Start the UDP Listen thread and queues
        """
        self.logger.info("UDP Listen Thread init")

        self.tUDPListenStop = threading.Event()

        self.tUDPListen = threading.Thread(target=self._UDPListenThread)
        self.tUDPListen.deamon = False

        try:
            self.tUDPListen.start()
        except:
            self.logger.exception("Failed to Start the UDP listen thread")

    def _LCRThread(self):
        """ LLAP Config Request thread
            Main logic for dealing with LCR's
            We check the incomming qLCRRequest and qLCRSerial
        """
        self.logger.info("tLCR: LCR thread started")
        
        while (not self.tLCRStop.is_set()):
            # TODO: move over LCR logic and refactor for queue's
            # do we have a request
            if not self.qLCRRequest.empty():
                self.logger.debug("tLCR: Got a request to process")
                try:
                    LCR = self.qLCRRequest.get(timeout=1)
                except Queue.Empty:
                    self.logger.debug("tLCR: Failed to get item from qLCRRequest")
                else:
                    # lets start processing it
                    # check the keepAwake first
                    if LCR['data'].get('keepAwake', None) == 1:
                        self.logger.debug("tLCR: keepAwake turned on")
                        self._LCRKeepAwake = 1
                    elif LCR['data'].get('keepAwake', None) == 0:
                        self.logger.debug("tLCR: keepAwake turned off")
                        self._LCRKeepAwake = 0
                    
                    if LCR['data'].get('toQuery', False):
                        pass
                    
                    
                    self.qLCRRequest.task_done()


            # no request so empty qLCRSerial unless we have a keepAwake
            while not self.qLCRSerial.empty():
                self.logger.debug("tLCR: Something in qLCRSerial")
                try:
                    llapMsg = self.qLCRSerial.get(timeout=1)
                except Queue.Empty:
                    self.logger.debug("tLCR: Failed to get item from qLCRSerial")
                else:
                    self.qLCRSerial.task_done()

            # wait a little
            self.tLCRStop.wait(0.1)

        self.logger.info("tLCR: Thread stopping")
        
    def _UDPSendTread(self):
        """ UDP Send thread
        """
        self.logger.info("tUDPSend: Send thread started")
        # setup the UDP send socket
        try:
            UDPSendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error, msg:
            self.logger.critical("tUDPSend: Failed to create scoekt. Error code : {} Message : {}".format(msg[0], msg[1]))
            # TODO: tUDPSend needs to stop here
            self.die()
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        sendPort = int(self.config.get('UDP', 'send_port'))
        
        while (not self.tUDPSendStop.is_set()):
            try:
                message = self.qUDPSend.get(timeout=30)     # block for up to 30 seconds
            except Queue.Empty:
                # UDP Send que was empty
                # extrem debug message
                # self.logger.debug("tUDPSend: queue is empty")
                pass
            else:
                self.logger.debug("tUDPSend: Got json to send: {}".format(message))
                try:
                    UDPSendSocket.sendto(message, ('<broadcast>', sendPort))
                    self.logger.debug("tUDPSend: Put message out via UDP")
                except socket.error, msg:
                    self.logger.warn("tUDPSend: Failed to send via UDP. Error code : {} Message: {}".format(msg[0], msg[1]))
                
                # tidy up
                self.qUDPSend.task_done()

            # TODO: tUDPSend thread is alive, wiggle a pin?

        self.logger.info("tUDPSend: Thread stopping")
        
    def _SerialThread(self):
        """ Serial Thread
        """
        self.logger.info("tSerial: Serial thread started")
        while (not self.tSerialStop.is_set()):
            # open the port
            try:
                self._serial.open()
                self.logger.info("tSerial: Opened the serial port")
            except serial.SerialException:
                self.logger.exception("tSerial: Failed to open port {}".format(self._serial.port))
                self.die()
            
            self.tSerialStop.wait(2)

            # do stuff
            while self._serial.isOpen():
                # extrem debug message
                # self.logger.debug("tSerial: check serial port")
                if self._serial.inWaiting():
                    char = self._serial.read()  # should not time out but we should check anyway
                    self.logger.debug("tSerial: RX:{}".format(char))
                
                    if char == 'a':
                        # this should be the start of a llap message
                        # read 11 more or time out
                        llapMsg = "a"
                        # TODO: better reaading of the 11,
                        # include restart if found another a
                        llapMsg += self._serial.read(11)
                        
                        # TODO: check llapMsg for valid LLAP chars

                        self.logger.debug("tSerial: RX:{}".format(llapMsg[1:]))
                        if llapMsg[1:3] == "??":
                            if llapMsg == "a??CONFIGME-" and self._LCRKeepAwake:
                                try:
                                    self._serial.write("a??HELLO----")
                                except Serial.SerialException, msg:
                                    self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
                            # we have a ?? message pass on to qLCRSerial
                            try:
                                self.qLCRSerial.put_nowait(llapMsg)
                            except Queue.Full:
                                self.logger.warn("tSerial: Failed to put {} on qLCRSerial as it's full".format(llapMsg))
                        else:
                            # not a configme llap
                            try:
                                self.qUDPSend.put_nowait(self.encodeLLAPJson(llapMsg, self.config.get('Serial', 'network')))
                            except Queue.Full:
                                self.logger.warn("tSeral: Failed to put {} on qUDPSend as it's full".format(llapMsg))
            
                # do we have anything to send
                if not self.qSerialOut.empty():
                    self.logger.debug("tSerial: got something to send")
                    try:
                        llapMsg = self.qSerialOut.get_nowait()
                        self._serial.write(llapMsg)
                        self.logger.debug("tSerial: TX:{}".format(llapMsg))
                        self.qSerialOut.task_done()
                    except Queue.Empty:
                        self.logger.debug("tSerial: failed to get item from queue")
                    except Serial.SerialException, msg:
                        self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
            
                # sleep for a little
                self.tSerialStop.wait(0.1)
            
            # port closed for some reason, if tSerialStop is set we will try repoening
            
        # close the port
        self.logger.info("tSerial: Closeing serial port")
        self._serial.close()
        
        self.logger.info("tSerial: Thread stoping")

    def _UDPListenThread(self):
        """ UDP Listen Thread
        """
        self.logger.info("tUDPListen: UDP listen thread started")
        
        try:
            UDPListenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            self.logger.exception("tUDPListen: Failed to create socket")
            self.die()

        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            UDPListenSocket.bind(('', int(self.config.get('UDP', 'listen_port'))))
        except socket.error:
            self.logger.exception("tUDPListen: Failed to bind port")
            self.die()
        
        self.logger.info("tUDPListen: listening")
        while (not self.tUDPListenStop.is_set()):
            (data, address) = UDPListenSocket.recvfrom(1024)
            self.logger.debug("tUDPListen: Received JSON: {} From: {}".format(data, address))
            jsonin = json.loads(data)
            
            if jsonin['type'] == "LLAP":
                self.logger.debug("tUDPListen: JSON of type LLAP, send out messages")
                # got a LLAP type json, need to generate the LLAP meassge and
                # put them on the TX que
                for command in jsonin['data']:
                    llapMsg = "a{}{}".format(jsonin['id'], command[0:9].upper())
                    while len(llapMsg) <12:
                        llapMsg += '-'
                    
                    # send to each network requested
                    if (jsonin['network'] == self.config.get('Serial', 'network') or
                        jsonin['network'] == "ALL"):
                        # yep its for serial
                        try:
                            self.qSerialOut.put_nowait(llapMsg)
                        except Queue.Full:
                            self.logger.debug("tUDPListen: Failed to put {} on qLCRSerial as it's full".format(llapMsg))
                        else:
                            self.logger.debug("tUDPListen Put {} on qSerialOut".format(llapMsg))

            elif jsonin['type'] == "LCR":
                # TODO: we have a LLAPConfigRequest pass in onto the LCR thread
                self.logger.debug("tUDPListen: JSON of type LCR, passing to qLCRRequest")
                try:
                    self.qLCRRequest.put_nowait(jsonin)
                except Queue.Full:
                    self.logger.debug("tUDPListen: Failed to put json on qLCRRequest")

            elif jsonin['type'] == "Server":
                # TODO: we have a SERVER json do stuff with it
                self.logger.debug("tUDPListen: JSON of type SERVER, passing to qServer")

        self.logger.info("tUDPListen: Thread stopping")
        try:
            UDPListenSocket.close()
        except socket.error:
            self.logger.exception("tUDPListen: Failed to close socket")
                
    def encodeLLAPJson(self, message, network=None):
        """Encode a single LLAP message into an outgoing JSON message
            """
        self.logger.debug("JSON: encodeing {} to json LLAP".format(message))
        jsonDict = {'type':"LLAP"}
        jsonDict['network'] = network if network else "DEFAULT"
        jsonDict['timestamp'] = strftime("%d %b %Y %H:%M:%S +0000", gmtime())
        jsonDict['id'] = message[1:3]
        jsonDict['data'] = [message[3:].strip("-")]

        jsonout = json.dumps(jsonDict)
        # extrem debugging
        # self.logger.debug("JSON: {}".format(jsonout))

        return jsonout
    
    def die(self):
        """For some reason we can not longer go forward
            Try cleaning up what we can and exit
        """
        self.logger.critical("DIE")
        # TODO: clean up what we can
        sys.exit(1)

# run code
if __name__ == "__main__" :
    app = LLAPServer()
    app.start()
    app.join()


















