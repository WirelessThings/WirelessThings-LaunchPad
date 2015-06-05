#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAPServer
    Copyright (c) 2014 Ciseco Ltd.
    
    Requires pySerial
    
    Author: Matt Lloyd
    
    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

"""
import sys
from time import time, sleep, gmtime, strftime
import os
import signal
import errno
import Queue
import argparse
import ConfigParser
import serial
import threading
import socket
import select
import json
import logging
import AT
import re
if sys.platform == 'win32':
    pass
else:
    from daemon import DaemonContext, pidlockfile
    import lockfile

"""
   Big TODO list
   
   LCR logic
    DONE: first pass at processing a request in and out
    DONE: check DTY
    DONE: timeouts from config or JSON
    TODO: Fix Processing EN{1-6} replies
    
   DONE: better serial read logic
   
   DONE: Catch Ctrl-C
   DONE: Clean up on quit code
   DONE: Clean up on die code
   
   Thread state monitor
       gpio state display
       DONE: restart dead threads
       DONE: restart dead serial
       restart dead socket ? how to check
       need to find a way to test broken threads are getting restarted
   
   "SERVER" messages
        DONE: status
        reboot
        stop
        config changes (local ENC and PANID)
        report AT settings on request
        change AT settings on request
        
        
   DONE: Set ATLH1 on start
   Improve checking and retries for ATLH1
   make ATLH1 permanent on command line option
   Read other AT settigns at launch and store in a memory config
   
   
   DONE: *nix Daemon behaviour
   windows service dehaviour
   
   self update via web
        started via a Server message
        
   Auto configure Encryption if set on server and flag confirmed from GUI
   Auto configure PANID
   
   Wake message logic
   configme enable/disable logic
   
   
"""

class LLAPServer():
    """Core logic and master thread control
        
    LLAPServer looks after the following threads
    Serial
    LCR
    UDP Send
    UDP Listen
    
    It starts by loading the LLAPServerConfig.cfg file
    Setting up debug out put and logging
    Then starts the threads for the various transport layers
    
    
    """

    _configFile = "./LLAPServer.cfg"
    _pidFile = None
    _pidFilePath = "./LLAPServer.pid"
    _pidFileTimeout = 5
    _background = False
    
    _SerialFailCount = 0
    _SerialFailCountLimit = 3
    _serialTimeout = 1     # serial port time out setting
    _UDPListenTimeout = 5   # timeout for UDP listen
    
    _version = 0.12

    _currentLCR = False
    devType = None
    _SerialDTYSync = False
    _LCRStartTime = 0
    _LCRCurrentTimeout = 0
    
    _validID = "ABCDEFGHIJKLMNOPQRSTUVWXYZ-#@?\\*"
    _validData = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-.:;<=>?@[\\\/]^_`{|}~"
    _encryptionCommandMatch = re.compile('^EN[1-6]')
    
    _state = ""
    Running = "Running"
    Error = "Error"
    
    _deviceStore = {}

    _ActionHelp = """
start = Starts as a background daemon/service
stop = Stops a daemon/service if running
restart = Restarts the daemon/service
status = Check if a LLAP transfer serveice is running
If none of the above are given and no daemon/service
is running then run in the current terminal
"""

    def __init__(self, logger=None):
        """Instantiation
            
        Setup basic transport, Queue's, Threads etc
        """
        if hasattr(sys,'frozen'): # only when running in py2exe this exists
            self._path = sys.prefix
        else: # otherwise this is a regular python script
            self._path = os.path.dirname(os.path.realpath(__file__))
        
        if not sys.platform == 'win32':
            self._signalMap = {
                               signal.SIGTERM: self._cleanUp,
                               signal.SIGHUP: self.terminate,
                               signal.SIGUSR1: self._reloadProgramConfig,
                              }
        
        self.tMainStop = threading.Event()
        self.qServer = Queue.Queue()
        
        # setup initial Logging
        logging.getLogger().setLevel(logging.NOTSET)
        self.logger = logging.getLogger('LLAPServer')
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.WARN)    # this should be WARN by default
        self._formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._ch.setFormatter(self._formatter)
        self.logger.addHandler(self._ch)
    
    def __del__(self):
        """Destructor
            
        Close any open threads, and transports
        """
        # TODO: shut down anything we missed
        pass
    
    def start(self):
        """Start by check in the args and sorting out run context foreground/service/daemon
           This is the main entry point for most start conditions
        """
        self.logger.info("Start")
        
        self._checkArgs()           # pull in the command line options
        
        if not self._checkDaemon():         # base on the command line argument stop|stop|restart as a daemon
            self.logger.debug("Exiting")
            return
        self.run()
        
        
        if not self._background:
            if not sys.platform == 'win32':
                try:
                    self.logger.info("Removing Lock file")
                    self._pidFile.release()
                except:
                    pass
    def _checkArgs(self):
        """Parse the command line options
        """
        parser = argparse.ArgumentParser(description='LLAP Server', formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('action', nargs = '?', choices=('start', 'stop', 'restart', 'status'), help =self._ActionHelp)
        #parser.add_argument('-u', '--noupdate',
        #                    help='disable checking for update',
        #                    action='store_false')
        parser.add_argument('-d', '--debug',
                            help='Enable debug output to console, overrides LLAPServer.cfg setting',
                            action='store_true')
        parser.add_argument('-l', '--log',
                            help='Override the console debug logging level, DEBUG, INFO, WARNING, ERROR, CRITICAL'
                            )
        parser.add_argument('-p', '--port',
                            help='Override the serial port given in LLAPServer.cfg'
                            )
                            
        self.args = parser.parse_args()
    
    def _checkDaemon(self):
        """ Based on the current os and command line arguments handle running as
            a background daemon or service
            returns 
                True if we should continue running
                False if we are done and should exit
        """
        if sys.platform == 'win32':
            # need a way to check if we are already running on win32
            self._background = False
            return True
        else:
            # must be *nix based, right?
            
            #setup pidfile checking
            self._pidFile = self._makePidlockfile(os.path.join(self._path, self._pidFilePath),
                                                  self._pidFileTimeout)
            
            if self.args.action == None:
                # run in foreground unless a daemon is all ready running
                
                # check for valid or stale pid file, if there is already a copy running somewhere we don't want to start again
                if self._isPidfileStale(self._pidFile):
                    self._pidFile.break_lock()
                    self.logger.debug("Removed Stale Lock")
                
                # create and lock a new pid file
                self.logger.info("Acquiring Lock file")
                try:
                    self._pidFile.acquire()
                except lockfile.LockTimeout:
                    self.logger.critical("Already running, exiting")
                    return False
                else:
                    # register our own signal handlers
                    for (signal_number, handler) in self._signalMap.items():
                        signal.signal(signal_number, handler)
                    
                    self._background = False
                    return True
                        
            elif self.args.action == 'start':
                # start as a daemon
                return self._dstart()
            elif self.args.action == 'stop':
                self._dstop()
                return False
            elif self.args.action == 'restart':
                self.logger.debug("Stoping old daemon")
                self._dstop()
                self.logger.debug("Starting new daemon")
                return self._dstart()
            elif self.args.action == 'status':
                self._dstatus()
                return False
                    
    def _dstart(self):
        """Kick off a daemon process
        """

        self._daemonContext = DaemonContext()
        self._daemonContext.stdin = open('/dev/null', 'r')
        self._daemonContext.stdout = open('/dev/null', 'w+')
        self._daemonContext.stderr = open('/dev/null', 'w+', buffering=0)
        self._daemonContext.pidfile = self._pidFile
        self._daemonContext.working_directory = self._path
        
        self._daemonContext.signal_map = self._signalMap
        if self._isPidfileStale(self._pidFile):
            self._pidFile.break_lock()
            self.logger.debug("Removed Stale Lock")

        try:
            self._daemonContext.open()
        except pidlockfile.AlreadyLocked:
            self.logger.warn("Already running, exiting")
            return False
        
        self._background = True
        return True

    def _dstop(self):
        """ Stop a running process base on PID file
        """
        if not self._pidFile.is_locked():
            self.logger.debug("Nothing to stop")
            return False
        
        if self._isPidfileStale(self._pidFile):
            self._pidFile.break_lock()
            self.logger.debug("Removed Stale Lock")
            return True
        else:
            pid = self._pidFile.read_pid()
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError, exc:
                self.logger.warn("Failed to terminate {}: {}: Try sudo".format(pid, exc))
                return False
            else:
                # we stopped something :)
                self.logger.debug("Stopped pid {}".format(pid))
                return True

    def _dstatus(self):
        """ Test the PID file to see if we are running some where
            Return 
                pid if running
                None if not
            """
        pid = None
        if self._isPidfileStale(self._pidFile):
            self._pidFile.break_lock()
            self.logger.debug("Removed Stale Lock")
        
        pid = self._pidFile.read_pid()
        if pid is not None:
            print("{} is running (PID {})".format(os.path.basename(__file__),pid))
        else:
            print("{} is not running".format(os.path.basename(__file__)))

        return pid

    def run(self):
        """Run Everything
           At this point the Args have been checked and everything is setup if
           we are running in the foreground or as a daemon/service
        """
        
        try:
            self._readConfig()          # read in the config file
            self._initLogging()         # setup the logging options
            self._initLCRThread()       # start the LLAPConfigRequest thread
            self._initUDPSendThread()   # start the UDP sender
            self.tMainStop.wait(1)
            self._initSerialThread()    # start the serial port thread
            self.tMainStop.wait(1)
            self._initUDPListenThread() # start the UDP listener
            
            self._state = self.Running
            
            # main thread looks after the server status for us
            while not self.tMainStop.is_set():
                # check threads are running
                if not self.tLCR.is_alive():
                    self.logger.error("tMain: LCR thread stopped")
                    self._state = self.Error
                    self.tMainStop.wait(1)
                    self._startLCR()
                    self.tMainStop.wait(1)
                    if self.tLCR.is_alive():
                        self._state = self.Running
            
                if not self.tUDPSend.is_alive():
                    self.logger.error("tMain: UDPSend thread stopped")
                    self._state = self.Error
                    self.tMainStop.wait(1)
                    self._startUDPSend()
                    self.tMainStop.wait(1)
                    if self.tUDPSend.is_alive():
                        self._state = self.Running
                            
                if not self.tSerial.is_alive():
                    self.logger.error("tMain: Serial thread stopped, wait 1 before trying to re-establish ")
                    self._state = self.Error
                    self.tMainStop.wait(1)
                    self._startSerail()
                    self.tMainStop.wait(1)
                    if self.tSerial.is_alive():
                        self._state = self.Running
                    else:
                        self._SerialFailCount += 1
                        if self._SerialFailCount > self._SerialFailCountLimit:
                            self.logger.error("tMain: Serial thread failed to recover after {} retries, Exiting".format(self._SerialFailCountLimit))
                            self.die()

                if not self.tUDPListen.is_alive():
                    self.logger.error("tMain: UDPListen thread stopped")
                    self._state = self.Error
                    self.tMainStop.wait(1)
                    self._startUDPListen()
                    self.tMainStop.wait(1)
                    if self.tUDPSend.is_alive():
                        self._state = self.Running
                
                # process any "Server" messages
                if not self.qServer.empty():
                    self.logger.debug("tMain: Processing Server JSON message")
                    try:
                        json = self.qServer.get_nowait()
                    except Queue.Empty():
                        pass
                    else:
                        self._processServerMessage(json)
                            
                # flash led's if GPIO debug
                self.tMainStop.wait(0.5)

        except KeyboardInterrupt:
            self.logger.info("Keyboard Interrupt - Exiting")
            self._cleanUp()
            sys.exit()
        self.logger.debug("Exiting")

    def _readConfig(self):
        """Read the server config file from disk
        """
        self.logger.info("Reading config files")
        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self._configFile))
        except:
            self.logger.error("Could Not Load Settings File")

        if not self.config.sections():
            self.logger.critical("No Config Loaded, Exiting")
            self.die()

    def _reloadProgramConfig(self):
        """ Reload the config file from disk
        """
        # TODO: do we want to be able reload config on SIGUSR1?
        pass

    def _initLogging(self):
        """ now we have the config file loaded and the command line args setup
            setup the loggers
        """
        self.logger.info("Setting up Loggers. Console output may stop here")

        # disable logging if no options are enabled
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
            self.logger.debug("Setting file debugger")
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
        """ Setup the Thread and Queues for handling LLAPConfigRequests
        """
        self.logger.info("LCR Thread init")

        self.qLCRRequest = Queue.Queue()
        self.qLCRSerial = Queue.Queue()
        
        self.tLCRStop = threading.Event()
        self.fAnsweredAll = threading.Event()
        self.fRetryFail = threading.Event()
        self.fTimeoutFail = threading.Event()
        self.fKeepAwake = threading.Event()
        self.fKeepAwake.clear()
        self.fTimeoutFail.clear()
        self.fRetryFail.clear()
        self.fAnsweredAll.clear()

        self._startLCR()
    
    def _startLCR(self):
        self.tLCR = threading.Thread(name='tLCR', target=self._LCRThread)
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
    
        self._startUDPSend()
        
    def _startUDPSend(self):
        self.tUDPSend = threading.Thread(name='tUDPSendThread', target=self._UDPSendTread)
        self.tUDPSend.daemon = False
        try:
            self.tUDPSend.start()
        except:
            self.logger.exception("Failed to Start the UDP send thread")

    def _initSerialThread(self):
        """ Setup the serial port and start the thread
        """
        self.logger.info("Serial port init")

        # serial port base on config file, thread handles opening and closing
        self._serial = serial.Serial()
        if (self.args.port):
            self._serial.port = self.args.port
        else:
            self._serial.port = self.config.get('Serial', 'port')
        self._serial.baud = self.config.get('Serial', 'baudrate')
        self._serial.timeout = self._serialTimeout
        
        # setup queue
        self.qSerialOut = Queue.Queue()
        self.qSerialToQuery = Queue.Queue()
        
        # setup thread
        self.tSerialStop = threading.Event()
        
        self._startSerail()
    
    def _startSerail(self):
        self.tSerial = threading.Thread(name='tSerial', target=self._SerialThread)
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

        self._startUDPListen()
        
    def _startUDPListen(self):
        self.tUDPListen = threading.Thread(name='tUDPListen', target=self._UDPListenThread)
        self.tUDPListen.deamon = False
        try:
            self.tUDPListen.start()
        except:
            self.logger.exception("Failed to Start the UDP listen thread")
    
    def _LCRThread(self):
        """ LLAP Config Request thread
            Main logic for dealing with LCR's
            We check the incoming qLCRRequest and qLCRSerial
        """
        self.logger.info("tLCR: LCR thread started")
        
        while (not self.tLCRStop.is_set()):
            # do we have a request
            if not self.qLCRRequest.empty():
                self.logger.debug("tLCR: Got a request to process")
                # if we are not in the middle of an LCR
                if not self._currentLCR:
                    # lets get it out the queue and start processing it
                    try:
                        self._currentLCR = self.qLCRRequest.get_nowait()
                    except Queue.Empty:
                        self.logger.debug("tLCR: Failed to get item from qLCRRequest")
                    else:
                        # check the keepAwake
                        if self._currentLCR['data'].get('keepAwake', None) == 1:
                            self.logger.debug("tLCR: keepAwake turned on")
                            self.fKeepAwake.set()
                        elif self._currentLCR['data'].get('keepAwake', None) == 0:
                            self.logger.debug("tLCR: keepAwake turned off")
                            self.fKeepAwake.clear()
                        
                        if self._currentLCR['data'].get('toQuery', False):
                            # make place for replies later
                            self._currentLCR['data']['replies'] = {}
                            # use a copy in case we are adding ENC stuff
                            toQuery = list(self._currentLCR['data']['toQuery'])
                            if self._currentLCR['data'].has_key('setENC'):
                                # TODO: need to perpend encryption key setup to the toQuery
                                if self.config.getboolean('Serial','encryption'):
                                    self.logger.debug("tLCR: auto setting encryption")
                                    toQuery.insert(0, {"command":"ENC", "value":"ON"})
                                    for (index, hex) in enumerate(list(self._chunkstring(self.config.get('Serial', 'encryption_key'), 6))):
                                        toQuery.insert(0, {"command":"EN{}".format(index+1), "value":hex})

                            # pass queries on to the serial thread to send out
                            try:
                                self.qSerialToQuery.put_nowait(toQuery)
                            except Queue.Full:
                                self.logger.debug("tLCR: Failed to put item onto toQuery as it's full")
                            else:
                                self.devType = self._currentLCR['data'].get('devType', None)
                                # reset flags
                                self.fAnsweredAll.clear()
                                self.fRetryFail.clear()
                                self.fTimeoutFail.clear()
                                # start timer
                                self._LCRCurrentTimeout = int(self._currentLCR['data'].get('timeout', self.config.get('LCR', 'timeout')))
                                self._LCRStartTime = time()
                                self.logger.debug("tLCR: started LCR timeout with period: {}".format(self._LCRCurrentTimeout))
                        else:
                            # no toQuery section, so reply with all done
                            self._LCRReturnLCR("PASS")
                        self.qLCRRequest.task_done()

            # do we have a reply from serial
            while not self.qLCRSerial.empty():
                self.logger.debug("tLCR: Something in qLCRSerial")
                try:
                    llapReply = self.qLCRSerial.get_nowait()
                except Queue.Empty:
                    self.logger.debug("tLCR: Failed to get item from qLCRSerial")
                else:
                    self.logger.debug("tLCR: Got {} to process".format(llapReply))
                    if self._currentLCR:
                        # we are working on a request check and store the reply
                        for q in self._currentLCR['data']['toQuery']:
                            if llapReply.strip('-').startswith(q['command']):
                                self._currentLCR['data']['replies'][q['command']] = {'value': q.get('value', ""),
                                                                                'reply': llapReply[len(q['command']):].strip('-')
                                                                                }
                                self.logger.debug("tLCR: Stored reply '{}':{}".format(q['command'], self._currentLCR['data']['replies'][q['command']]))
                        # and reset the timeout
                        self.logger.debug("tLCR: Reset timeout to 0")
                        self._LCRStartTime = time()
                    else:
                        # drop it
                        pass
                    self.qLCRSerial.task_done()
            
            # check the timeout
            if self._currentLCR and ((time() - self._LCRStartTime) > self._LCRCurrentTimeout):
                # if expired cancel the toQuery in tSerial
                self.logger.debug("tLCR: LCR timeout expired")
                self.fTimeoutFail.set()

            # no point checking flags if we are not in the middle of a request
            if self._currentLCR:
                # has the serial thread finished getting all the query answers
                if self.fAnsweredAll.is_set():
                    # finished toQuery ok
                    self.logger.debug("tLCR: Serial answered so send out json")
                    self._LCRReturnLCR("PASS")
                elif self.fRetryFail.is_set():
                    # failed due to a message retry issue
                    self.logger.warn("tLCR: Failed current LCR due to retry count")
                    self._LCRReturnLCR("FAIL_RETRY")
                elif self.fTimeoutFail.is_set():
                    # failed due to expired timeout
                    self.logger.warn("tLCR: Failed current LCR due to timeout")
                    while not self.qSerialToQuery.empty():
                        try:
                            self.qSerialToQuery.get()
                            self.logger.debug("tLCR: removed stale query from qSerialToQuery")
                        except Queue.Empty:
                            pass
                    
                    self._LCRReturnLCR("FAIL_TIMEOUT")
            
            # wait a little
            self.tLCRStop.wait(0.5)
            
        self.logger.info("tLCR: Thread stopping")
        return

    def _LCRReturnLCR(self, state):
        # prep the reply
        self._currentLCR['timestamp'] = strftime("%d %b %Y %H:%M:%S +0000", gmtime())
        self._currentLCR['network'] = self.config.get('Serial', 'network')
        self._currentLCR['keepAwake'] = 1 if self.fKeepAwake.is_set() else 0
        self._currentLCR['data']['state'] = state

        # encode json
        jsonout = json.dumps(self._currentLCR)

        # send to UDP thread
        try:
            self.qUDPSend.put_nowait(jsonout)
        except Queue.Full:
            self.logger.warn("tLCR: Failed to put {} on qUDPSend as it's full".format(llapMsg))
        else:
            self.logger.debug("tLCR: Sent LCR reply to qUDPSend")
            # and clear LCR and SentAll flag
            self._currentLCR = False

    def _UDPSendTread(self):
        """ UDP Send thread
        """
        self.logger.info("tUDPSend: Send thread started")
        # setup the UDP send socket
        try:
            UDPSendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error, msg:
            self.logger.critical("tUDPSend: Failed to create socket, Exiting. Error code : {} Message : {} ".format(msg[0], msg[1]))
            self.die()
        
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        sendPort = int(self.config.get('UDP', 'send_port'))
        
        while (not self.tUDPSendStop.is_set()):
            try:
                message = self.qUDPSend.get(timeout=1)     # block for up to 1 seconds
            except Queue.Empty:
                # UDP Send queue was empty
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
                    
        self.logger.info("tUDPSend: Thread stopping")
        try:
            UDPSendSocket.close()
        except socket.error:
            self.logger.exception("tUDPSend: Failed to close socket")
        return
            
    def _SerialThread(self):
        """ Serial Thread
        """
        self.logger.info("tSerial: Serial thread started")
        self._SerialToQueryState = 0
        self._SerialToQuery = []
        self.tSerialStop.wait(1)
        try:
            while (not self.tSerialStop.is_set()):
                # open the port
                try:
                    self._serial.open()
                    self.logger.info("tSerial: Opened the serial port")
                except serial.SerialException:
                    self.logger.exception("tSerial: Failed to open port {} Exiting".format(self._serial.port))
                    self._serial.close()
                    self.die()
                
                self.tSerialStop.wait(0.1)
                
                # we clear out any stale serial messages that might be in the buffer
                self._serial.flushInput()
                
                # check the ATLH settings
                self._SerialCheckATLH()
                
                # main serial processing loop
                while self._serial.isOpen() and not self.tSerialStop.is_set():
                    # extrem debug message
                    # self.logger.debug("tSerial: check serial port")
                    if self._serial.inWaiting():
                        self._SerialReadIncomingLLap()
                    
                    # do we have anything to send
                    if not self.qSerialOut.empty():
                        self.logger.debug("tSerial: got something to send")
                        try:
                            llapMsg = self.qSerialOut.get_nowait()
                            self._serial.write(llapMsg)
                        except Queue.Empty:
                            self.logger.debug("tSerial: failed to get item from queue")
                        except Serial.SerialException, e:
                            self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
                        else:
                             self.logger.debug("tSerial: TX:{}".format(llapMsg))
                             self.qSerialOut.task_done()
                
                    # sleep for a little
                    if self._SerialToQueryState or self._serial.inWaiting():
                        self.tSerialStop.wait(0.01)
                    else:
                        self.tSerialStop.wait(0.1)
                
                # port closed for some reason (or tSerialStop), if tSerialStop is not set we will try reopening
        except IOError:
            self.logger.exception("tSerail: IOError on serial port")
        
        # close the port
        self.logger.info("tSerial: Closing serial port")
        self._serial.close()
        
        self.logger.info("tSerial: Thread stoping")
        return
                    
    def _SerialCheckATLH(self):
        """ check and possible set the the ATLH setting on the radio
            if command line XX the make permanent (ATWR)
        """
        self.logger.info("tSerial: Setting ATLH1")

        self._serial.flushInput()
    
        at = AT.AT(self._serial, self.logger, self.tSerialStop)
        # TODO: make this way more reliable
        if at.enterATMode():
            if at.sendATWaitForOK("ATLH1"):
                if at.sendATWaitForOK("ATAC"):
                    if 0:
                        at.sendATWaitForOK("ATWR")
            # TODO: check/set out PANID and encryption settings as per config
            
            at.leaveATMode()
    
    def _SerialReadIncomingLLap(self):
        char = self._serial.read()  # should not time out but we should check anyway
        self.logger.debug("tSerial: RX:{}".format(char))
    
        if char == 'a':
            # this should be the start of a llap message
            # read 11 more or time out
            llapMsg = "a"
            count = 0
            while count < 11:
                char = self._serial.read()
                if not char:
                    self.logger.debug("tSerial: RX:{}".format(char))
                    return
            
                if char == 'a':
                    # start again and
                    count = 0
                    llapMsg = "a"
                    self.logger.debug("tSerial: RX:{}".format(char))
                elif (count == 0 or count == 1) and char in self._validID:
                    # we have a vlaid ID
                    llapMsg += char
                    count += 1
                elif count >= 2 and char in self._validData:
                    # we have a valid data
                    llapMsg += char
                    count +=1
                else:
                    self.logger.debug("tSerial: RX:{}".format(llapMsg[1:] + char))
                    return
    
            self.logger.debug("tSerial: RX:{}".format(llapMsg[1:]))
            
            if len(llapMsg) == 12:  # just double check length
                if llapMsg[1:3] == "??":
                    self._SerialProcessQQ(llapMsg[3:].strip("-"))
                else:
                    # not a configme llap so send out via UDP LLAP
                    try:
                        self.qUDPSend.put_nowait(self.encodeLLAPJson(llapMsg, self.config.get('Serial', 'network')))
                    except Queue.Full:
                        self.logger.warn("tSerial: Failed to put {} on qUDPSend as it's full".format(llapMsg))

    def _SerialProcessQQ(self, llapMsg):
        """ process an incoming ?? llap message
        """
        # has the timeout expired
        if not self.fTimeoutFail.is_set():
            if self._SerialToQueryState:
                # was it a reply to our DTY test
                if self.devType and (not self._SerialDTYSync):
                    # we should have a reply to DTY
                    if llapMsg.startswith("DTY"):
                        if llapMsg[3:] == self.devType:
                            self._SerialDTYSync = True
                            self.logger.debug("tSerial: Confirmed DTY, Send next toQuery, State: {}".format(self._SerialToQueryState))
                            if not self._SerialSendLCRQuery():
                                # failed to send question (serial or retry error)
                                if self.fRetryFail.is_set():
                                    # was a retry fail
                                    # stop processing toQuery
                                    self._SerialToQueryState = 0
                            return
        
                # check reply was to the last question
                if llapMsg.startswith(self._SerialToQuery[self._SerialToQueryState-1]['command']) or (self._encryptionCommandMatch.match(self._SerialToQuery[self._SerialToQueryState-1]['command']) and llapMsg == "ENACK"):
                    
                    # special case for encryption
                    if self._encryptionCommandMatch.match(self._SerialToQuery[self._SerialToQueryState-1]['command']):
                        llapMsg = self._SerialToQuery[self._SerialToQueryState-1]['command'] + llapMsg
                    
                    # reduce the state count and reset retry count
                    self._SerialToQueryState -= 1
                    self._SerialRetryCount = 0

                    # store the reply
                    try:
                        self.qLCRSerial.put_nowait(llapMsg)
                    except Queue.Full:
                        self.logger.warn("tSerial: Failed to put {} on qLCRSerial as it's full".format(llapMsg))
                    
                    # if we have replies for all state == 0:
                    if self._SerialToQueryState == 0:
                        # sent and received all
                        self.fAnsweredAll.set()
                        self.logger.debug("tSerial: Go answers for all toQuery")
                    # else we have a another query to send
                    else:
                        # send next
                        self.logger.debug("tSerial: Send next toQuery, State: {}".format(self._SerialToQueryState))
                        if not self._SerialSendLCRQuery():
                            # failed to send question (serial error)
                            pass
                # else if was not our answer so send it again
                elif llapMsg == "CONFIGME":
                    if self.devType:
                        # out of sync should we recheck DTY?
                        self._SerialDTYSync = False
                        self.logger.debug("tSerial: Checking DTY again before sending next toQuery")
                        self._SerialSendDTY()
                        return
                    else:
                        # send last again
                        self.logger.debug("tSerial: Retry toQuery, State: {}".format(self._SerialToQueryState))
                        if not self._SerialSendLCRQuery():
                            # failed to send question (serial or retry error)
                            if self.fRetryFail.is_set():
                                # was a retry fail
                                # stop processing toQuery
                                self._SerialToQueryState = 0
                                return
        
            elif llapMsg == "CONFIGME":
                # do we have a waiting query and can we send one
                try:
                    self._SerialToQuery = self.qSerialToQuery.get_nowait()
                except Queue.Empty:
                    pass
                else:
                    self._SerialToQuery.reverse()
                    self._SerialToQueryState = len(self._SerialToQuery)
                    self.fAnsweredAll.clear()
                    self.fRetryFail.clear()
                    # clear retry count
                    self._SerialRetryCount = 0
                    # new query should we check DTY
                    if self.devType:
                        self.logger.debug("tSerial: Checking DTY before sending first toQuery")
                        self._SerialSendDTY()
                        return
                    else:
                        # send first
                        self.logger.debug("tSerial: Send first toQuery, State: {}".format(self._SerialToQueryState))
                        if not self._SerialSendLCRQuery():
                            # failed to send question (serial or retry error)
                            pass
        elif self._SerialToQueryState:
            # yes the time out expired, clear down any current toQuery
            self.logger.debug("tSerial: toQuery Timed out")
            self._SerialToQueryState = 0
        
            
        # only thing left now would be a CONFIGME so do we need to send a keepAwake
        if llapMsg == "CONFIGME" and self.fKeepAwake.is_set():
            try:
                self._serial.write("a??HELLO----")
            except Serial.SerialException, e:
                self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
            else:
                self.logger.debug("tSerial: TX:a??HELLO-----")
            return

    def _SerialSendLCRQuery(self):
        """ send out the next query in the current LCR
        """
        # check retry count before sending
        if self._SerialRetryCount < int(self.config.get('LCR', 'single_query_retry_count')):
            llapToSend = "a??{}{}".format(self._SerialToQuery[self._SerialToQueryState-1]['command'],
                                           self._SerialToQuery[self._SerialToQueryState-1].get('value', "")
                                           )
            while len(llapToSend) < 12:
                llapToSend += "-"
            try:
                self._serial.write(llapToSend)
            except Serial.SerialException, e:
                self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
                return False
            else:
                self.logger.debug("tSerial: TX:{}".format(llapToSend))
                self._SerialRetryCount += 1
                return True
        self.logger.debug("tSerial: toQuery failed on retry count, letting tLCR know")
        self.fRetryFail.set()
        return False

    def _SerialSendDTY(self):
        """ Ask a LLAP+ device it devType
        """
        try:
          self._serial.write("a??DTY------")
        except Serial.SerialException, e:
          self.logger.warn("tSerial: failed to write to the serial port {}: {}".format(self._serial.port, e))
          return False
        else:
          self.logger.debug("tSerial: TX:a??DTY------")
          self._SerialDTYSync = False
          return True

    def _UDPListenThread(self):
        """ UDP Listen Thread
        """
        self.logger.info("tUDPListen: UDP listen thread started")
        
        try:
            UDPListenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            self.logger.exception("tUDPListen: Failed to create socket, Exiting")
            self.die()

        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if (self.args.debug) and sys.platform == 'darwin':
            UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        
        try:
            UDPListenSocket.bind(('', int(self.config.get('UDP', 'listen_port'))))
        except socket.error:
            self.logger.exception("tUDPListen: Failed to bind port, Exiting")
            self.die()
        
        UDPListenSocket.setblocking(0)
        
        self.logger.info("tUDPListen: listening")
        while not self.tUDPListenStop.is_set():
            datawaiting = select.select([UDPListenSocket], [], [], self._UDPListenTimeout)
            if datawaiting[0]:
                (data, address) = UDPListenSocket.recvfrom(2048)
                self.logger.debug("tUDPListen: Received JSON: {} From: {}".format(data, address))
                jsonin = json.loads(data)
                
                # TODO: error checking, dict should have keys for netork
                if (jsonin['network'] == self.config.get('Serial', 'network') or
                    jsonin['network'] == "ALL"):
                    # yep its for our network or "ALL"
                    # TODO: error checking, dict should have keys for type
                    if jsonin['type'] == "LLAP":
                        self.logger.debug("tUDPListen: JSON of type LLAP, send out messages")
                        # got a LLAP type json, need to generate the LLAP message and
                        # put them on the TX queue
                        # TODO: error checking, dict should have keys for data
                        for command in jsonin['data']:
                            llapMsg = "a{}{}".format(jsonin['id'], command[0:9].upper())
                            while len(llapMsg) <12:
                                llapMsg += '-'
                            
                            try:
                                self.qSerialOut.put_nowait(llapMsg)
                            except Queue.Full:
                                self.logger.debug("tUDPListen: Failed to put {} on qLCRSerial as it's full".format(llapMsg))
                            else:
                                self.logger.debug("tUDPListen Put {} on qSerialOut".format(llapMsg))

                    elif jsonin['type'] == "LCR" and self.config.getboolean('LCR', 'lcr_enable'):
                        # we have a LLAPConfigRequest pass in onto the LCR thread
                        # TODO: error checking, dict should have keys for data
                        self.logger.debug("tUDPListen: JSON of type LCR, passing to qLCRRequest")
                        try:
                            self.qLCRRequest.put_nowait(jsonin)
                        except Queue.Full:
                            self.logger.debug("tUDPListen: Failed to put json on qLCRRequest")

                    elif jsonin['type'] == "Server":
                        # we have a SERVER json do stuff with it
                        self.logger.debug("tUDPListen: JSON of type SERVER, passing to qServer")
                        try:
                            self.qServer.put(jsonin)
                        except Queue.Full():
                            self.logger.debug("tUDPListen: Failed to put json on qServer")
 
        self.logger.info("tUDPListen: Thread stopping")
        try:
            UDPListenSocket.close()
        except socket.error:
            self.logger.exception("tUDPListen: Failed to close socket")
        return

    def _processServerMessage(self, message):
        message['timestamp'] = strftime("%d %b %Y %H:%M:%S +0000", gmtime())
        message['network'] = self.config.get('Serial', 'network')
        message['state'] = self._state
        if message.has_key('data'):
            result = {}
            if message['data'].has_key('request'):
                for request in message['data']['request']:
                    if request == "deviceStore":
                        result['deviceStore'] = self._deviceStore
                    # TODO: implement other server "requests"
                    elif request == "PANID":
                        result['PANID'] = self.config.get('Serial', 'panid')
                    elif request == "encryptionSet":
                        result['encryptionSet'] = self.config.getboolean('Serial', 'encryption')
            elif message['data'].has_key('set'):
                for set in message['data']['set']:
                    # TODO: implement "set" requests
                    pass
            message['data']['result'] = result
                
        try:
            # just report state
            self.qUDPSend.put(json.dumps(message))
        except Queue.Full:
            self.logger.debug("tMain: Failed to put {} on qUDPSend as it's full".format(message))
        else:
            self.logger.debug("tMain: Put {} on qUDPSend".format(message))

    
    def encodeLLAPJson(self, message, network=None):
        """Encode a single LLAP message into an outgoing JSON message
            """
        self.logger.debug("tSerial: JSON: encoding {} to json LLAP".format(message))
        jsonDict = {'type':"LLAP"}
        jsonDict['network'] = network if network else "DEFAULT"
        jsonDict['timestamp'] = strftime("%d %b %Y %H:%M:%S +0000", gmtime())
        jsonDict['id'] = message[1:3]
        jsonDict['data'] = [message[3:].strip("-")]

        jsonout = json.dumps(jsonDict)
        self._updateDeviceStore(jsonDict)
        # extrem debugging
        # self.logger.debug("JSON: {}".format(jsonout))

        return jsonout
    
    def _updateDeviceStore(self, message):
        self._deviceStore[message['id']] = {'data': message['data'][0], 'timestamp': message['timestamp']}
    
    def _chunkstring(self, string, length):
        return (string[0+i:length+i] for i in range(0, len(string), length))
    
    # TODO: catch errors and add logging
    def _makePidlockfile(self, path, acquire_timeout):
        """ Make a PIDLockFile instance with the given filesystem path. """
        if not isinstance(path, basestring):
            error = ValueError("Not a filesystem path: %(path)r" % vars())
            raise error
        if not os.path.isabs(path):
            error = ValueError("Not an absolute path: %(path)r" % vars())
            raise error
        lockfile = pidlockfile.TimeoutPIDLockFile(path, acquire_timeout)

        return lockfile

    def _isPidfileStale(self, pidfile):
        """ Determine whether a PID file is stale.
            
            Return ``True`` (“stale”) if the contents of the PID file are
            valid but do not match the PID of a currently-running process;
            otherwise return ``False``.
            
            """
        result = False
        
        pidfile_pid = pidfile.read_pid()
        if pidfile_pid is not None:
            try:
                os.kill(pidfile_pid, signal.SIG_DFL)
            except OSError, exc:
                if exc.errno == errno.ESRCH:
                    # The specified PID does not exist
                    result = True
        
        return result
    
    def _cleanUp(self, signal_number=None, stack_frame=None):
        """ clean up on exit
        """
        # first stop the main thread from try to restart stuff
        self.tMainStop.set()
        # now stop the other threads
        try:
            self.tUDPListenStop.set()
            self.tUDPListen.join()
        except:
            pass
        try:
            self.tSerialStop.set()
            self.tSerial.join()
        except:
            pass
        try:
            self.tLCRStop.set()
            self.tLCR.join()
        except:
            pass
        try:
            self.tUDPSendStop.set()
            self.tUDPListen.join()
        except:
            pass
        
        if not self._background:
            if not sys.platform == 'win32':
                try:
                    self.logger.info("Removing Lock file")
                    self._pidFile.release()
                except:
                    pass

    def terminate(self, signal_number, stack_frame):
        """ Signal handler for end-process signals.
            :Return: ``None``
            
            Signal handler for the ``signal.SIGTERM`` signal. Performs the
            following step:
            
            * Raise a ``SystemExit`` exception explaining the signal.
            
            """
        exception = SystemExit(
                               "Terminating on signal %(signal_number)r"
                               % vars())
        raise exception

    def die(self):
        """For some reason we can not longer go forward
            Try cleaning up what we can and exit
        """
        self.logger.critical("DIE")
        self._cleanUp()

        sys.exit(1)

# run code
if __name__ == "__main__" :
    app = LLAPServer()
    app.start()
