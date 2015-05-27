#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAP ConfigMe
    Copyright (c) 2014 Ciseco Ltd.
    
    Author: Matt Lloyd
    
    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    
"""

import Tkinter as tk
import ttk
import sys
import os
import argparse
import socket
import select
import json
import ConfigParser
import tkMessageBox
import threading
import Queue
import string
import re
from time import sleep, asctime, time
import logging
import uuid
from collections import OrderedDict
import itertools

"""
    Big TODO list
    
    DONE: JSON over UDP
    
    DONE: UDP open sockets
    
    DONE: JSON encode outgoing messages
    DONE: JSON decode incoming messages
    
    DONE: JSON debug window
    Pretty JSON format for window?
    
    DONE: type: SERVER status check on start up
        basic PING
        
    DONE: use logger for debug output
    
    DONE: timeouts wait windows base on timeout's sent with LCR
    
    DONE: keepAwake via JSON's
    
    DONE: check replies for state, PASS, FAIL_RETRY, FAIL_TIMEOUT
    
    DONE: disable next button while waiting for query
    
    read AT settings for PANID and ENCRYPTION from server and offer as defaults to the user on a new device
    
    get JSON device file from network
    
    offer suggested settings based on json
    
    UUID in LCR JSON's so only listen for my own replies
        either another field or don't hard code stages via id
    
    if more that one server on the network offer LCR target dropdown
    
    fix self.die()
    
"""


INTRO = """Welcome to LLAP Config me wizard
    
Please wait while we try to reach a LLAP Transfer service"""

INTRO1 = """Welcome to LLAP Config me wizard
    
A LLAP Transfer service has be found running on this network.

Please select a service to use from the list bellow"""

CONFIG = """Select your device config options"""

END = """Your device has been configured"""

PRESSTEXT = """Please press the Config button on your device"""
PRESSTEXT1 = """Communicating with device"""

INTERVALTEXT = """Use the slider to select a reporting period for the device. 
A shorter period will result in reduce battery life for a battery powered device"""

ENCRYPTIONTEXT = """Encryption long description"""

WARNINGTEXT = "Warning: This ID has been used before."

NEWDEVICETEXT = """This is a new device. Network setting will be automatically set to match your hub"""
NEWDEVICEIDTEXT = "A new ID has been automatically assigned, to override please click change"

SETTINGMISSMATCHTEXT = """The network settings on your device do not match this hub, do you wish to update them?"""
MISSMATCHINFOTEXT = """The network settings on your device do not match this hub. This could be either the PANID or Encryption, to have the automatically updated to match this hubs setting just check the box"""

class LLAPCongfigMeClient:
    """
        LLAP ConfigMe Client Class
        Handles display of wizard interface for configuring devices
        pass requests onto LLAPConfigMeCore
    """

    _version = 0.12
    
    _configFileDefault = "LLAPCM_defaults.cfg"
    _configFile = "LLAPCM.cfg"
    _myNodesFile = "MyNodes.json"
    _infoIconFile = "noun_80697_cc.gif"
    
    _rows = 19
    _rowHeight = 28
    _widthMain = 604
    _heightMain = (_rows*_rowHeight)+4
    _widthSerial = 600
    _heightSerial = 200
    
    # how long to wait for a reply before asking user to press button again in seconds
    _timeout = 40
    _devIDInputs = []
    _encryptionKeyInput = 0
    _lastLCR = []
    _keepAwake = 0
    _currentFrame = None
    _servers = {}
    _serverButtons = {}
    _serverQueryJSON = json.dumps({"type": "Server", "network": "ALL"})
    _configState = 0
    
    _validID = "ABCDEFGHIJKLMNOPQRSTUVWXYZ-#@?\\*"
    _validData = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-.:;<=>?@[\\\/]^_`{|}~"
    _periodUnits = {"T":"Milli seconds", "S":"Seconds", "M":"Minutes", "H":"Hours", "D":"Days"}

    def __init__(self):
        """
            setup variables
        """
        self._running = False

        logging.getLogger().setLevel(logging.NOTSET)
        self.logger = logging.getLogger('LLAPServer')
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.WARN)    # this should be WARN by default
        self._formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self._ch.setFormatter(self._formatter)
        self.logger.addHandler(self._ch)
    
        # JSON Debug window Q
        self.qJSONDebug = Queue.Queue()
        # LCR Reply Q, Incoming JSON's from the server
        self.qLCRReply = Queue.Queue()
        # flag to show a server msg has been received
        self.fServerUpdate = threading.Event()
        self.fWaitingForReply = threading.Event()

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

    def on_excute(self):
        """
            entry point for running
        """
        self._checkArgs()
        self._readConfig()
        self._initLogging()
        self._loadDevices()
        
        self._running = True

        # run the GUI's
        self._runConfigMe()
        self._cleanUp()

    def _runConfigMe(self):
        self.logger.debug("Running Main GUI")
        self.master = tk.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self._endConfigMe)
        self.master.geometry(
                 "{}x{}+{}+{}".format(self._widthMain,
                                      self._heightMain,
                                      self.config.get('LLAPCM',
                                                      'window_width_offset'),
                                      self.config.get('LLAPCM',
                                                      'window_height_offset')
                                      )
                             )

        self.master.title("LLAP Config Me v{}".format(self._version))
        self.master.resizable(0,0)
        
        self._initTkVariables()
        self._initValidationRules()
        
        if self.args.debug or self.config.getboolean('Debug', 'gui_json'):
            self._jsonWindowDebug()
        
        self._initUDPListenThread()
        self._initUDPSendThread()
        
        # TODO: are UDP threads running
        if (not self.tUDPListen.isAlive() and not self.tUDPSend.isAlive()):
            self.logger.warn("UDP Threads not running")
            # TODO: do we have an error form the UDP to show?
        else:
            # dispatch a server status request
            self.qUDPSend.put(self._serverQueryJSON)
            
            self._displayIntro()
            
            self.master.mainloop()
    
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

    def _UDPSendTread(self):
        """ UDP Send thread
        """
        self.logger.info("tUDPSend: Send thread started")
        # setup the UDP send socket
        try:
            UDPSendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error, msg:
            self.logger.critical("tUDPSend: Failed to create socket. Error code : {} Message : {}".format(msg[0], msg[1]))
            # TODO: tUDPSend needs to stop here
            # TODO: need to send message to user saying could not open socket
            self.die()
            return
        
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPSendSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        sendPort = int(self.config.get('UDP', 'send_port'))
        
        while not self.tUDPSendStop.is_set():
            try:
                message = self.qUDPSend.get(timeout=1)     # block for up to 30 seconds
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
                else:
                    self.qJSONDebug.put([message, "TX"])
                # tidy up

                self.qUDPSend.task_done()

            # TODO: tUDPSend thread is alive, wiggle a pin?

        self.logger.info("tUDPSend: Thread stopping")
        try:
            UDPSendSocket.close()
        except socket.error:
            self.logger.exception("tUDPSend: Failed to close socket")
        return

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

    def _UDPListenThread(self):
        """ UDP Listen Thread
        """
        self.logger.info("tUDPListen: UDP listen thread started")
        
        try:
            UDPListenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            self.logger.exception("tUDPListen: Failed to create socket, stopping")
            # TODO: need to send message to user saying could not create socket object
            self.die()
            return

        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sys.platform == 'darwin':
            UDPListenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        
        try:
            UDPListenSocket.bind(('', int(self.config.get('UDP', 'listen_port'))))
        except socket.error:
            self.logger.exception("tUDPListen: Failed to bind port")
            # TODO: need to send message to user saying could not open socket
            self.die()
            return
        UDPListenSocket.setblocking(0)
        
        self.logger.info("tUDPListen: listening")
        while not self.tUDPListenStop.is_set():
            ready = select.select([UDPListenSocket], [], [], 3)  # 3 second time out using select
            if ready[0]:
                (data, address) = UDPListenSocket.recvfrom(2048)
                self.logger.debug("tUDPListen: Received JSON: {} From: {}".format(data, address))
                # TODO: Test its actually json/catch errors
                jsonin = json.loads(data)
                self.qJSONDebug.put([data, "RX"])
                # TODO: Check for keys before trying to use them
                if jsonin['type'] == "LLAP":
                    self.logger.debug("tUDPListen: JSON of type LLAP")
                    # got a LLAP type json, need to generate the LLAP message and
                    # TODO: we should pass on LLAP type to the JSON window if enabled
                    pass
                elif jsonin['type'] == "LCR":
                    # we have a LLAPConfigRequest reply pass it back to the GUI to deal with
                    self.logger.debug("tUDPListen: JSON of type LCR, passing to qLCRReply")
                    try:
                        self.qLCRReply.put_nowait(jsonin)
                    except Queue.Full:
                        self.logger.debug("tUDPListen: Failed to put json on qLCRReply")

                elif jsonin['type'] == "Server":
                    # TODO: we have a SERVER json do stuff with it
                    self.logger.debug("tUDPListen: JSON of type SERVER")
                    self._updateServerDetailsFromJSON(jsonin)
            
        self.logger.info("tUDPListen: Thread stopping")
        try:
            UDPListenSocket.close()
        except socket.error:
            self.logger.exception("tUDPListen: Failed to close socket")
        return
    
    def _initTkVariables(self):
        self.logger.debug("Init Tk Variables")
        # any tk variables we need to keep permanent
        self._readingScale = [tk.IntVar(), tk.StringVar(), tk.StringVar()]
        self._readingScale[0].trace_variable('w', self._updateIntervalOnScaleChange)
        
        self._infoIcon = tk.PhotoImage(file=self._infoIconFile)
        self._devIDWarning = tk.StringVar()
        self._settingMissMatchVar = tk.IntVar()
        self._settingMissMatchVar.trace_variable('w', self._updateMissMatchSettings)
        # init the entry variables we will need to reset between each run
        self._initEntryVariables()
        
    def _initEntryVariables(self):
        self.logger.debug("Init entry Variables")
        # format for each entry is as follows
        # 'command': [current Value, old Value, type Off Output]
        #
        # type of Output
        # this is based on the format field from the json
        # with the exception of ENKEY
        # type is used in conjunction with how these fields are displayed for user
        # input and how we process that for LCR output
        # most are just straight copy outputs but some like ONOF and ENKEY require special handling
        self.entry = {
                      "CHDEVID" : [tk.StringVar(), tk.StringVar(), 'ID'],
                      "PANID" : [tk.StringVar(), tk.StringVar(), 'ID'],
                      "RETRIES" : [tk.StringVar(), tk.StringVar(), 'Int'],
                      "INTVL" : [tk.StringVar(), tk.StringVar(), 'Period'],
                      "WAKEC" : [tk.StringVar(), tk.StringVar(), 'Int'],
                      "SLEEPM" : [tk.IntVar(), tk.IntVar(), 'SleepMode'],
                      "SNL" : [tk.StringVar(), tk.StringVar(), 'ReadOnlyHex'],
                      "SNH" : [tk.StringVar(), tk.StringVar(), 'ReadOnlyHex'],
                      "ENC" : [tk.IntVar(), tk.IntVar(), 'ONOFF'],
                      "ENKEY" : [tk.StringVar(), tk.StringVar(), 'ENKey'],
                      "RSSI" : [tk.IntVar(), tk.IntVar(), 'Int']
                     }
        self.entry['CHDEVID'][0].trace_variable('w', self._checkDevIDList)
        self._settingMissMatchVar.set(0)
                      
    def _displayIntro(self):
        self.logger.debug("Display Intro Page")
        self.iframe = tk.Frame(self.master, name='introFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.iframe.pack()
        self._currentFrame = 'introFrame'
        
        self._buildGrid(self.iframe)
        
        tk.Label(self.iframe, name='introText', text=INTRO
                 ).grid(row=1, column=0, columnspan=6, rowspan=4)

        self._checkServerCount = 0
        self._checkServer = True
        self.master.after(1000, self._checkServerUpdate)
    
    def _checkServerUpdate(self):
#        self.logger.debug("Checking server reply flag")
        if self.fServerUpdate.is_set():
            # flag set, re-draw buttons
            self._updateServerList()
            # clear flag and schedule next check
            self.fServerUpdate.clear()
        
        
        if self._checkServerCount == 5:
            # send out another status ping
            self.qUDPSend.put(self._serverQueryJSON)
        elif self._checkServerCount == 10:
            # let user know we are still looking but have not found anything yet
            if len(self._servers) == 0:
                pass

            # send out another query and reset count
            self._checkServerCount = 0
            self.qUDPSend.put(self._serverQueryJSON)
        
        self._checkServerCount += 1
        if self._checkServer:
            # carry on checking until user moves from first page
            self.master.after(1000, self._checkServerUpdate)

    def _updateServerList(self):
        self.logger.debug("Updating Server list buttons")
        self.iframe.children['introText'].config(text=INTRO1)
        for network, server in self._servers.items():
            # if we don't all-ready have a button create a new one
            if network not in self._serverButtons.keys():
                self._serverButtons[network] = tk.Button(self.iframe,
                                                         name="n{}".format(network),
                                                         text=network,
                                                         command=lambda n=network:self._displayPressButton(n),
                                                         state=tk.ACTIVE if server['state'] == "Running" or server['state'] == "RUNNING" else tk.DISABLED
                                                         )
                self._serverButtons[network].grid(row=5+len(self._serverButtons),
                                                  column=1,
                                                  columnspan=4, sticky=tk.E+tk.W)
            else:
              # need to update button state
              self._serverButtons[network].config(state=tk.ACTIVE if server['state'] == "Running" or server['state'] == "RUNNING" else tk.DISABLED
                                                  )

    def _displayPressButton(self, network, reset=False):
        self.logger.debug("Displaying PressButton")
        
        self._network = network
        
        self.master.children[self._currentFrame].pack_forget()
        
    
        self.pframe = tk.Frame(self.master, name='pressFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.pframe.pack()
        self._currentFrame = 'pressFrame'
        
        self._buildGrid(self.pframe)
        
        if not reset:
            pt = PRESSTEXT
        else:
            pt = PRESSTEXT1
        tk.Label(self.pframe, name='pressText', text=pt
                 ).grid(row=1, column=0, columnspan=6, rowspan=4)

        tk.Button(self.pframe, text='Back',
                  command = self._startOver,
                  ).grid(row=0, column=1, sticky=tk.W)
        if not reset:
            self.master.after(1, self._queryType)
    
    def _displaySimpleConfig(self, fromConfig=False):
        self.logger.debug("Displaying Device type based simple config screen")
        self.master.children[self._currentFrame].pack_forget()
                
        self.sframe = tk.Frame(self.master, name='simpleFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.sframe.pack()
        self._currentFrame = 'simpleFrame'

        self._buildGrid(self.sframe)
        r = 0
        # device name and rssi (topbar)
        tk.Label(self.sframe,
                 text="{}".format(self.devices[self.device['id']]['Name'])
                 ).grid(row=r, column=0, columnspan=6)
        tk.Label(self.sframe,
                 text="RSSI: -{}".format(self.entry['RSSI'][0].get()),
                 ).grid(row=r, column=4)
    
        # buttons
        tk.Button(self.sframe, text='Back', state=tk.ACTIVE,
                  command=self._startOver,
                  ).grid(row=r, column=1, sticky=tk.W)
        tk.Button(self.sframe, name='next', text='Done',
                 command=self._sendConfigRequest
                 ).grid(row=self._rows-4, column=2, columnspan=2,
                        sticky=tk.E+tk.W)
        tk.Button(self.sframe, name='reset', text='Reset to Defaults',
                  command=self._resetDefautls
                  ).grid(row=self._rows-3, column=2, columnspan=2,
                         sticky=tk.E+tk.W)
        tk.Button(self.sframe, text='Advanced Config',
                  command=self._displayConfig
                  ).grid(row=self._rows-2, column=2, columnspan=2,
                         sticky=tk.E+tk.W)
    
        # description
        r += 1
        tk.Label(self.sframe,
                 text="{}".format(self.devices[self.device['id']]['Description']),
                 wraplength=self._widthMain/6*4,
                 ).grid(row=r, column=1, columnspan=4, rowspan=3)
        r += 1
        tk.Button(self.sframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("Description"),
                  image=self._infoIcon
                  ).grid(row=r, column=5, sticky=tk.W)
                  
        # new device Label
        if self.device['newDevice']:
            r += 2
            tk.Label(self.sframe, text=NEWDEVICETEXT,
                     wraplength=self._widthMain/6*4
                     ).grid(row=r, column=1, columnspan=4, rowspan=2)
        

        # device ID
        r += 2
        tk.Label(self.sframe, text="Device ID:").grid(row=r, column=1,
                                                      sticky=tk.E)
        tk.Label(self.sframe, textvariable=self.entry['CHDEVID'][0]
                 ).grid(row=r, column=3, sticky=tk.W+tk.E)
        tk.Button(self.sframe, text="Change", command=self._displayChangeDevID
                  ).grid(row=r, column=4)
        tk.Button(self.sframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("CHDEVID"),
                  image=self._infoIcon,
                  ).grid(row=r, column=5, sticky=tk.W)
        if self.device['newDevice']:
            r += 1
            tk.Label(self.sframe, text=NEWDEVICEIDTEXT
                     ).grid(row=r, column=1, columnspan=4, sticky=tk.W+tk.E)

        r += 2 # start row for next set of options
        
        # if supports message
        for option in self.devices[self.device['id']]['Options']:
            if option['Command'] == "MSG":
                # display message filed
                tk.Label(self.sframe, text="Message text:"
                         ).grid(row=r, column=1, sticky=tk.E)
                e = tk.Entry(self.sframe,
                             textvariable=self.entry[option['Command']][0],
                             name=option['Command'].lower()
                             )
                e.grid(row=r, column=3, columnspan=2, sticky=tk.W+tk.E)
                e.config(validate='key',
                         invalidcommand='bell',
                         validatecommand=self.vUpper)
                self._devIDInputs.append(e)
                tk.Button(self.sframe, text='More Info', state=tk.ACTIVE,
                          command=lambda: self._displayMoreInfo("MSG"),
                          image=self._infoIcon
                          ).grid(row=r, column=5, sticky=tk.W)
                r +=2
    
        # if cyclic device show slider
        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
            self._updateScaleAndDescriptionFromPeriod(self.entry['INTVL'][0].get(), not fromConfig)
            tk.Label(self.sframe, text="Reading Interval:"
                     ).grid(row=r, column=1, sticky=tk.E)
            tk.Scale(self.sframe, variable=self._readingScale[0],
                     orient=tk.HORIZONTAL, showvalue=0,
                     from_=0, to=len(self._readingPeriods), resolution=1
                     ).grid(row=r, column=2, columnspan=2, sticky=tk.W+tk.E)
            tk.Button(self.sframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("Interval"),
                      image=self._infoIcon
                      ).grid(row=r, column=5, sticky=tk.W)
            tk.Label(self.sframe, textvariable=self._readingScale[1],
                     wraplength=self._widthMain/6
                     ).grid(row=r, column=4, columnspan=1, sticky=tk.W+tk.E)
            tk.Label(self.sframe, textvariable=self._readingScale[2],
                     wraplength=self._widthMain/6*4
                     ).grid(row=r+1, column=1, columnspan=4, rowspan=3, sticky=tk.W+tk.E)
            r += 5

        # if not a new device does the network settings match?
        if not self.device['newDevice'] and self.device['settingsMissMatch']:
            tk.Label(self.sframe, text="Update network settings:"
                     ).grid(row=r, column=1, columnspan=2, sticky=tk.E)
            tk.Checkbutton(self.sframe, variable=self._settingMissMatchVar
                           ).grid(row=r, column=3, columnspan=2)
            tk.Button(self.sframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("MissMatch"),
                      image=self._infoIcon,
                      ).grid(row=r, column=5, sticky=tk.W)
            tk.Label(self.sframe, text=SETTINGMISSMATCHTEXT,
                     wraplength=self._widthMain/6*4
                     ).grid(row=r+1, column=1, columnspan=4, rowspan=2)
            r += 3
            
            
    def _updateIntervalOnScaleChange(self, *args):
        if self._readingScale[0].get() != len(self._readingPeriods):
            if self.entry['INTVL'][0].get() != self._readingPeriods[self._readingScale[0].get()]['Period']:
                self.entry['INTVL'][0].set(self._readingPeriods[self._readingScale[0].get()]['Period'])
                self.entry['SLEEPM'][0].set(1)
        try:
            self._readingScale[1].set("{}".format(self._parseIntervalToString(self.entry['INTVL'][0].get())))
            self._readingScale[2].set("{}.\r {}".format(
                                        self._readingPeriods[self._readingScale[0].get()]['Description'],
                                        self._estimateLifeTimeForPeriod(self.entry['INTVL'][0].get(), self.device['id'])
                                                                              )
                                      )
        except:
            self._readingScale[1].set("Custom Period")
            self._readingScale[2].set("To set a custom reporting period please use the \"Advanced Config\" option below".format(self._parseIntervalToString(self.entry['INTVL'][0].get())))

    def _updateScaleAndDescriptionFromPeriod(self, intval, setCycle=True):
        for (index,period) in enumerate(self._readingPeriods):
            if intval == "000S":
                # period no set use default from json
                self._readingScale[0].set(self.devices[self.device['id']]['ReadingPeriod'])
                self._readingScale[1].set(self._readingPeriods[self._readingScale[0].get()]['Description'])
                self._readingScale[2].set("{}.\r {}".format(
                                            self._readingPeriods[self._readingScale[0].get()]['Description'],
                                            "?")
                                          )
                if setCycle:
                    self.entry['SLEEPM'][0].set(1)
                return
            elif intval == period['Period']:
                self._readingScale[0].set(index)
                self._readingScale[1].set("{}".format(self._parseIntervalToString(self.entry['INTVL'][0].get())))
                self._readingScale[2].set("{}.\r {}".format(
                                            self._readingPeriods[self._readingScale[0].get()]['Description'],
                                            self._estimateLifeTimeForPeriod(self.entry['INTVL'][0].get(), self.device['id'])
                                                                                  )
                                          )
                if setCycle:
                    self.entry['SLEEPM'][0].set(1)
                return
        
        self._readingScale[0].set(len(self._readingPeriods))
        self._readingScale[1].set("Custom Period {}".format(self._parseIntervalToString(self.entry['INTVL'][0].get())))
        self._readingScale[2].set("You have chosen a custom period of {}.\r {}".format(
                                    self._parseIntervalToString(self.entry['INTVL'][0].get()),
                                    self._estimateLifeTimeForPeriod(self.entry['INTVL'][0].get(), self.device['id'])
                                                                                                             )
                                 )

    def _parseIntervalToString(self, period):
        return "{} {}".format(int(period[:3]), self._periodUnits[period[3:]])

    def _estimateLifeTimeForPeriod(self, period, deviceID):
        return "Expected life will be {}".format("?")
    
    def _getNextFreeID(self):
        try:
            for id in itertools.product(string.ascii_uppercase, repeat=2):
                if ''.join(id) not in sorted(self._servers[self._network]['data']['result']['deviceStore'].keys()):
                    return ''.join(id)
        except:
            return "??"

    def _updateMissMatchSettings(self, *args):
        try:
            if not self.device['newDevice']:
                    if self._settingMissMatchVar.get() == 1:
                        self.entry['PANID'][0].set(self._servers[self._network]['data']['result']['PANID'])
                        if self._servers[self._network]['data']['result']['encryptionSet']:
                            self.device['setENC'] = True
                        else:
                            self.device['setENC'] = False
                    else:
                        self.entry['PANID'][0].set(self.entry['PANID'][1].get())
                        self.device['setENC'] = False
        except:
            pass
    
    def _displayMoreInfo(self, subject):
        self.logger.debug("Displaying more info for {}".format(subject))
        
        infoText = None
        infoFormat = None
        
        if subject == "Description":
            infoText = self.devices[self.device['id']]['Description']
        elif subject == "Interval":
            infoText = INTERVALTEXT
        elif subject == "MissMatch":
            infoText = MISSMATCHINFOTEXT
        elif subject == "Encryption":
            infoText = ENCRYPTIONTEXT
            infoFormat = "ENKey"
        else:
            # check LLAP Generic Commands, Cyclic Commands, device Actions and device Options all in one go
            commandList = (self._llapGenericCommands +
                           self._llapCyclicCommands +
                           self.devices[self.device['id']]['Actions'] +
                           self.devices[self.device['id']]['Options']
                           )
                           
            for command in commandList:
                if subject == command['Command']:
                    infoText = command['Description']
                    if command.has_key('Format'):
                        infoFormat = command['Format']

        position = self.master.geometry().split("+")
        
        self.moreInfoWindow = tk.Toplevel()
        self.moreInfoWindow.geometry("+{}+{}".format(
                                                    int(position[1])+self._widthMain/6,
                                                    int(position[2])+self._heightMain/6
                                                    )
                                    )
            
        self.moreInfoWindow.title("Info")

        self.miframe = tk.Frame(self.moreInfoWindow, name='moreInfoFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain/2,
                               height=self._heightMain/4)
        self.miframe.pack()

        tk.Label(self.miframe, text=infoText,
                 wraplength=self._widthMain/2
                 ).pack()

        if infoFormat:
            tk.Label(self.miframe, text="Format: {}".format(infoFormat)).pack()

        tk.Button(self.miframe, text="Dismiss",
                  command=self.moreInfoWindow.destroy
                  ).pack()
    
    def _displayChangeDevID(self):
        self.logger.debug("Displaying change DevID screen")
        self.master.children[self._currentFrame].pack_forget()
                
        self.dframe = tk.Frame(self.master, name='chdevidFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.dframe.pack()
        self._currentFrame = 'chdevidFrame'

        self._buildGrid(self.dframe)

        # device name and rssi (topbar)
        tk.Label(self.dframe,
                 text="{}".format(self.devices[self.device['id']]['Name'])
                 ).grid(row=0, column=0, columnspan=6)
        tk.Label(self.dframe,
                 text="RSSI: -{}".format(self.entry['RSSI'][0].get()),
                 ).grid(row=0, column=4)
    
        # buttons
        tk.Button(self.dframe, text='Back', state=tk.ACTIVE,
                  command=lambda: self._displaySimpleConfig(True),
                  ).grid(row=0, column=1, sticky=tk.W)

        # description and RSSI
        tk.Label(self.dframe,
                 text="Enter a device ID below",
                 wraplength=self._widthMain/6*4,
                 ).grid(row=1, column=1, columnspan=4, rowspan=3)

    
        tk.Label(self.dframe, text="Device ID:"
                 ).grid(row=4, column=1, sticky=tk.E)
        self._devIDInputs.append(tk.Entry(self.dframe,
                                          textvariable=self.entry['CHDEVID'][0],
                                          width=20,
                                          validate='key',
                                          invalidcommand='bell',
                                          validatecommand=self.vDevID,
                                          name='chdevid'
                                         )
                                )
        self._devIDInputs[-1].grid(row=4, column=3, columnspan=2, sticky=tk.W)
        tk.Label(self.dframe, textvariable=self._devIDWarning,
                 wraplength=self._widthMain/6*4
                 ).grid(row=5, column=1, columnspan=4)
        tk.Label(self.dframe, text="Previous ID's seen by this hub and there last message\r If you wish to reuse an ID your can select it form below."
                 ).grid(row=6, column=1, rowspan=2, columnspan=4)
    
        self._devIDListbox = tk.Listbox(self.dframe, selectmode=tk.SINGLE)
        try:
            # try to split get a device store list from our know server
            ds = self._servers[self._network]['data']['result']['deviceStore']
        except:
            pass
        else:
            ods = OrderedDict(sorted(ds.items(), key=lambda t: t[0]))
            index = 0
            for id, data in ods.items():
                self._devIDListbox.insert(index,
                                          "id: {}, data: {}, time: {}".format(id,
                                                                              data['data'],
                                                                              data['timestamp']
                                                                              )
                                          )
                index +=1
            
            self._devIDListbox.bind('<<ListboxSelect>>', self._onDevIDselect)

        self._devIDListbox.grid(row=8, column=1, columnspan=4,
                                rowspan=9, sticky=tk.E+tk.W+tk.N+tk.S)
    
    def _onDevIDselect(self, evt):
        w = evt.widget
        w.selection_clear(0, w.size())
    
    def _checkDevIDList(self, *args):
        if self._currentFrame == "chdevidFrame":
            try:
                if self.entry['CHDEVID'][0].get() in self._servers[self._network]['data']['result']['deviceStore'].keys():
                    self._devIDWarning.set(WARNINGTEXT)
                else:
                    self._devIDWarning.set("")
            except:
                pass

    def _displayConfig(self):
        self.logger.debug("Displaying Device type based config screen")
        self.master.children[self._currentFrame].pack_forget()
                
        self.cframe = tk.Frame(self.master, name='configFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.cframe.pack()
        self._currentFrame = 'configFrame'

        self._buildGrid(self.cframe)
        
        # device name and rssi (topbar)
        tk.Label(self.cframe,
                 text="{}".format(self.devices[self.device['id']]['Name'])
                 ).grid(row=0, column=0, columnspan=6)
        tk.Label(self.cframe,
                 text="RSSI: -{}".format(self.entry['RSSI'][0].get()),
                 ).grid(row=0, column=4)
                 
        # buttons
        tk.Button(self.cframe, text='Back', state=tk.ACTIVE,
                  command=lambda: self._displaySimpleConfig(True),
                  ).grid(row=0, column=1, sticky=tk.W)
        tk.Button(self.cframe, text='Encryption Settings',
                  command=self._displayAdvance
                  ).grid(row=self._rows-2, column=2, columnspan=2,
                         sticky=tk.E+tk.W)

        # description text
        tk.Label(self.cframe, text=CONFIG).grid(row=1, column=0, columnspan=6)
        
        # generic config options
        tk.Label(self.cframe, text="Generic Commands"
                 ).grid(row=2, column=0, columnspan=3)
                 
        tk.Label(self.cframe, text="Device ID").grid(row=3, column=0, columnspan=3)
        tk.Label(self.cframe, text="CHDEVID").grid(row=4, column=0, sticky=tk.E)
        self._devIDInputs.append(tk.Entry(self.cframe,
                                          textvariable=self.entry['CHDEVID'][0],
                                          width=20,
                                          validate='key',
                                          invalidcommand='bell',
                                          validatecommand=self.vDevID,
                                          name='chdevid'
                                         )
                                )
        self._devIDInputs[-1].grid(row=4, column=1, columnspan=2, sticky=tk.W)
        tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("CHDEVID"),
                  image=self._infoIcon,
                  ).grid(row=4, column=2, sticky=tk.E)
                 
        tk.Label(self.cframe, text="Pan ID").grid(row=5, column=0, columnspan=3)
        tk.Label(self.cframe, text="PANID").grid(row=6, column=0, sticky=tk.E)
        tk.Entry(self.cframe, textvariable=self.entry['PANID'][0], width=20,
                 validate='key',
                 invalidcommand='bell',
                 validatecommand=self.vUpper,
                 ).grid(row=6, column=1, columnspan=2, sticky=tk.W)
        tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("PANID"),
                  image=self._infoIcon,
                  ).grid(row=6, column=2, sticky=tk.E)
         
        tk.Label(self.cframe, text="Retries for Announcements"
                 ).grid(row=7, column=0, columnspan=3)
        tk.Label(self.cframe, text="RETRIES").grid(row=8, column=0, sticky=tk.E)
        tk.Entry(self.cframe, textvariable=self.entry['RETRIES'][0], width=20
                 ).grid(row=8, column=1, columnspan=2, sticky=tk.W)
        tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("RETRIES"),
                  image=self._infoIcon,
                  ).grid(row=8, column=2, sticky=tk.E)
        
        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
            # cyclic config options
            tk.Label(self.cframe, text="Cyclic Commands"
                     ).grid(row=10, column=0, columnspan=3)
            tk.Label(self.cframe, text="Sleep Interval"
                     ).grid(row=11, column=0, columnspan=3)
            tk.Label(self.cframe, text="INTVL").grid(row=12, column=0, sticky=tk.E)
            tk.Entry(self.cframe, textvariable=self.entry['INTVL'][0], width=20,
                     validate='key',
                     invalidcommand='bell',
                     validatecommand=self.vUpper,
                    ).grid(row=12, column=1, columnspan=2, sticky=tk.W)
            tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("INTVL"),
                      image=self._infoIcon,
                      ).grid(row=12, column=2, sticky=tk.E)
            
            tk.Label(self.cframe, text="Battery Wake Count"
                     ).grid(row=13, column=0, columnspan=3)
            tk.Label(self.cframe, text="WAKEC").grid(row=14, column=0, sticky=tk.E)
            tk.Entry(self.cframe, textvariable=self.entry['WAKEC'][0], width=20,
                    ).grid(row=14, column=1, columnspan=2, sticky=tk.W)
            tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("WAKEC"),
                      image=self._infoIcon,
                      ).grid(row=14, column=2, sticky=tk.E)
        
            tk.Label(self.cframe, text="Enable Cyclic Sleep"
                     ).grid(row=15, column=0, columnspan=3)
            tk.Label(self.cframe, text="CYCLE").grid(row=16, column=0, sticky=tk.E)
            tk.Checkbutton(self.cframe, variable=self.entry['SLEEPM'][0]
                          ).grid(row=16, column=1, columnspan=2, sticky=tk.W)
            tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("CYCLE"),
                      image=self._infoIcon,
                      ).grid(row=16, column=2, sticky=tk.E)
        elif self.devices[self.device['id']]['SleepMode'] == "Interrupt":
            # Interrupt sleep devices
            tk.Label(self.cframe, text="Interrupt Sleep"
                     ).grid(row=10, column=0, columnspan=3)
            tk.Label(self.cframe, text="SLEEP").grid(row=11, column=0, sticky=tk.E)
            tk.Checkbutton(self.cframe, variable=self.entry['SLEEPM'][0]
                          ).grid(row=11, column=1, columnspan=2, sticky=tk.W)
            tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo("SLEEP"),
                      image=self._infoIcon,
                      ).grid(row=11, column=2, sticky=tk.E)
        
        # device config options
        tk.Label(self.cframe,
                 text="Device specific options".format(self.devices[self.device['id']]['Name'])
                 ).grid(row=2, column=3, columnspan=3)
        r = 1
        for n in self.devices[self.device['id']]['Options']:
            
            tk.Label(self.cframe, text=n['Description']
                     ).grid(row=2+r, column=3, columnspan=3)
            tk.Label(self.cframe, text=n['Command']
                     ).grid(row=3+r, column=3, sticky=tk.E)
            if n['Format'] == "ONOFF":
                e = tk.Checkbutton(self.cframe, variable=self.entry[n['Command']][0],
                                   onvalue="ON", offvalue="OFF",
                                   name=n['Command'].lower()
                                   )
                e.grid(row=3+r, column=4, columnspan=2, sticky=tk.W)
            else:
                e = tk.Entry(self.cframe, textvariable=self.entry[n['Command']][0],
                             name=n['Command'].lower()
                             )
                e.grid(row=3+r, column=4, columnspan=2, sticky=tk.W)
                if n['Format'] == "Int":
                    e.config(validate='key',
                             invalidcommand='bell',
                             validatecommand=self.vInt)
                elif n['Format'] == "String":
                    e.config(validate='key',
                             invalidcommand='bell',
                             validatecommand=self.vUpper)
                elif n['Format'] == "ID":
                    e.config(validate='key',
                             invalidcommand='bell',
                             validatecommand=self.vDevID)
                    self._devIDInputs.append(e)
            tk.Button(self.cframe, text='More Info', state=tk.ACTIVE,
                      command=lambda: self._displayMoreInfo(n['Command']),
                      image=self._infoIcon,
                      ).grid(row=3+r, column=5, sticky=tk.E)
                    
            r += 2

    def _entryCopy(self):
        for key, value in self.entry.items():
            value[1].set(value[0].get())

    def _displayAdvance(self):
        """Advance config diag to show Serial number and set ENC"""
        # TODO: rearrange to fit long ENKEY box
        # TODO: should we also get FVER and display that?
        self.logger.debug("Display advance config screen")
    
        position = self.master.geometry().split("+")
            
        self.advanceWindow = tk.Toplevel()
        self.advanceWindow.geometry("+{}+{}".format(
                                                     int(position[1])+self._widthMain/6,
                                                     int(position[2])+self._heightMain/6
                                                     )
                                     )
                                     
        self.advanceWindow.title("Advance config")
    
        self.aframe = tk.Frame(self.advanceWindow, name='advanceFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain/6,
                               height=self._heightMain/6)
        self.aframe.pack()
        
        self._buildGrid(self.aframe, False, True)

        tk.Label(self.aframe, text="Advance configuration options"
                 ).grid(row=0, column=0, columnspan=6)
        
        tk.Label(self.aframe, text="Serial Number (read only)"
                 ).grid(row=1, column=0, columnspan=3)
    
        tk.Label(self.aframe, text="High Bytes").grid(row=2, column=0, columnspan=3)
        tk.Label(self.aframe, text="SNH").grid(row=3, column=0, sticky=tk.E)
        tk.Entry(self.aframe, textvariable=self.entry['SNH'][0], width=20,
                 state=tk.DISABLED
                 ).grid(row=3, column=1, columnspan=2, sticky=tk.W)
        tk.Button(self.aframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("SNH"),
                  image=self._infoIcon,
                  ).grid(row=3, column=2, sticky=tk.E)
    
        tk.Label(self.aframe, text="Low Bytes").grid(row=4, column=0, columnspan=3)
        tk.Label(self.aframe, text="SNL").grid(row=5, column=0, sticky=tk.E)
        tk.Entry(self.aframe, textvariable=self.entry['SNL'][0], width=20,
                 state=tk.DISABLED
                 ).grid(row=5, column=1, columnspan=2, sticky=tk.W)
        tk.Button(self.aframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("SNL"),
                  image=self._infoIcon,
                  ).grid(row=5, column=2, sticky=tk.E)
        
        tk.Label(self.aframe, text="Encryption Options"
                 ).grid(row=1, column=3, columnspan=3)
        tk.Button(self.aframe, text='More Info', state=tk.ACTIVE,
                  command=lambda: self._displayMoreInfo("Encryption"),
                  image=self._infoIcon,
                  ).grid(row=1, column=5)
    
        tk.Label(self.aframe, text="Enable Encryption"
                 ).grid(row=2, column=3, columnspan=3)
        tk.Label(self.aframe, text="ENC").grid(row=3, column=3, sticky=tk.E)
        tk.Checkbutton(self.aframe, variable=self.entry['ENC'][0]
                       ).grid(row=3, column=4, columnspan=2, sticky=tk.W)

    
        tk.Label(self.aframe, text="Encryption Key (set Only)"
                 ).grid(row=4, column=3, columnspan=3)
        tk.Label(self.aframe, text="EN[1-6]").grid(row=5, column=3, sticky=tk.E)
        self._encryptionKeyInput = tk.Entry(self.aframe,
                                            textvariable=self.entry['ENKEY'][0],
                                            width=33,
                                            validate='key',
                                            invalidcommand='bell',
                                            validatecommand=self.vEnKey,
                                            name='enkey')
                                            
        self._encryptionKeyInput.grid(row=5, column=4, columnspan=2, sticky=tk.W)



        tk.Button(self.aframe, text="Done", command=self._checkAdvance
                  ).grid(row=7, column=2, columnspan=2)
    
    def _displayEnd(self):
        self.logger.debug("Displaying end screen")
    
        self.master.children[self._currentFrame].pack_forget()

        self.eframe = tk.Frame(self.master, name='endFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.eframe.pack()
        self._currentFrame = 'endFrame'
        
        self._buildGrid(self.eframe)
        
        tk.Label(self.eframe, text=END).grid(row=1, column=0, columnspan=6,
                                              rowspan=2)
                                              
        tk.Button(self.eframe, text='Start Over', command=self._startOver
                  ).grid(row=4, column=2, columnspan=2, sticky=tk.E+tk.W)

    # validation rules

    # valid percent substitutions (from the Tk entry man page)
    # %d = Type of action (1=insert, 0=delete, -1 for others)
    # %i = index of char string to be inserted/deleted, or -1
    # %P = value of the entry if the edit is allowed
    # %s = value of entry prior to editing
    # %S = the text string being inserted or deleted, if any
    # %v = the type of validation that is currently set
    # %V = the type of validation that triggered the callback
    #      (key, focusin, focusout, forced)
    # %W = the tk name of the widget

    def _initValidationRules(self):
        self.logger.debug("Setting up GUI validation Rules")
        self.vUpper = (self.master.register(self.validUpper), '%d', '%P', '%S')
        self.vDevID = (self.master.register(self.validDevID), '%d',
                       '%P', '%W', '%P', '%S')
        self.vInt = (self.master.register(self.validInt), '%d', '%s', '%S')
        self.vHex = (self.master.register(self.validHex), '%d', '%s', '%S')
        self.vEnKey = (self.master.register(self.validEncryptionKey), '%d',
                       '%P', '%W', '%P', '%S')
    
    def validUpper(self, d, P, S):
        if S.islower():
            return False
        return True
            
    def validInt(self, d, s, S):
        if d == '0':
            return True
        if S.isdigit():
            return True
        else:
            return False

    def validHex(self, d, s, S):
        try:
            int(S, 16)          # is is a valid hex char
            return True
        except ValueError:
            return False
        return False
    
    def validEncryptionKey(self, d, P, W, s, S):
        valid = False
        if d == '0' or d == '-1':
            return True
        try:
            int(S, 16)          # is is a valid hex char
            valid = True
        except ValueError:
            return False
        
        if S.islower() and (len(P) <= 32):  # we already know is a HEX digit
            self.entry[W.split('.')[-1].upper()][0].set(P.upper())
            self.master.after_idle(self.vEnKeySet)
        elif valid and (len(P) <= 32):
            return True
        else:
            return False
    
    def validDevID(self, d, P, W, s, S):
        valid = False
        validChar = ['#', '@', '\\', '*'] # as of llap 2.0 - and ? cannot be set
        for c in validChar:
            if S.startswith(c):
                valid = True
        
        if d == '0' or d == '-1':
            return True
        elif S.islower() and (len(P) <= 2):
            self.entry[W.split('.')[-1].upper()][0].set(P.upper())
            self.master.after_idle(self.vdevSet)
        elif (S.isupper() or valid) and (len(P) <= 2):
            return True
        else:
            return False
    
    def vdevSet(self):
        for e in self._devIDInputs:
            e.icursor(e.index(tk.INSERT)+1)
            e.config(validate='key')

    def vEnKeySet(self):
        self._encryptionKeyInput.icursor(self._encryptionKeyInput.index(tk.INSERT)+1)
        self._encryptionKeyInput.config(validate='key')

    def _startOver(self):
        self.logger.debug("Starting over")
        self._stopKeepAwake()
        self.master.children[self._currentFrame].pack_forget()
        self.iframe.pack()
        self._currentFrame = 'introFrame'
        self._configState = 0
        self.device['newDevice'] = False
        self.device['setENC'] = False
        self.fWaitingForReply.clear()
        # clear out entry variables
        self._initEntryVariables()
    
    def _resetDefautls(self):
        self._displayPressButton(self.device['network'], reset=True)
        query = [
                 {'command': "LLAPRESET"},
                 {'command': "CHDEVID"}
                ]
                
        self.logger.debug("Setting keepAwake")
        self._keepAwake = 1

        self._configState = 5
        lcr = {"type": "LCR",
               "network":self.device['network'],
               "data":{
                       "id": str(uuid.uuid4()),
                       "timeout": self.config.get('LCR', 'timeout'),
                       "keepAwake":self._keepAwake,
                       "devType": self.device['DTY'],
                       "toQuery": query
                       }
              }
                  
        self._lastLCR.append(lcr)
        self._sendRequest(lcr)

    def _displayProgress(self):
        self.logger.debug("Displaying progress pop up")
        
        # disable current Next Button
        if self._currentFrame is not "pressFrame" and self._currentFrame is not "introFrame":
            self.master.children[self._currentFrame].children['next'].config(state=tk.DISABLED)
        
        if self._currentFrame != "pressFrame":
            # display a popup progress bar window
            position = self.master.geometry().split("+")
            
            self.progressWindow = tk.Toplevel()
            self.progressWindow.geometry("+{}+{}".format(
                                                 int(position[1])+self._widthMain/4,
                                                 int(position[2])+self._heightMain/4
                                                         )
                                         )
                
            self.progressWindow.title("Working")

            tk.Label(self.progressWindow,
                     text="Communicating with device please wait").pack()

            self.progressBar = ttk.Progressbar(self.progressWindow,
                                               orient="horizontal", length=200,
                                               mode="indeterminate")
            self.progressBar.pack()
            self.progressBar.start()
        else:
            # use the progress bar in the pressFrame
            self.progressBar = ttk.Progressbar(self.pframe,
                                               orient="horizontal", length=200,
                                               mode="indeterminate")
            self.progressBar.grid(row=7, column=1, columnspan=4)
            self.progressBar.start()
                
    def _checkAdvance(self):
        self.logger.debug("Checking advance input")
        if len(self.entry['ENKEY'][0].get()) == 32 or len(self.entry['ENKEY'][0].get()) == 0:
            self.advanceWindow.destroy()
        else:
            # let user know KEY needs to be 0 or 32
            tkMessageBox.showerror("Encryption Key Length",
                                   ("Encryption key needs to be 32 characters"
                                    "long to set a new one or empty to leave unchanged"))
    
    def _sendConfigRequest(self):
        self.logger.debug("Sending config request to device")
        # TODO: add a line here to disable NEXT button on cfame and advance
        query = []
        for command, value in self.entry.items():
            self.logger.debug("Checking {}: {} != {}".format(command, value[0].get(), value[1].get()))
            if not value[0].get() == value[1].get():
                query = self._entryAppend(query, command, value)
        
        query.append({'command': "REBOOT"}) # we always send at least a reboot

        self._keepAwake = 0
        self._configState = 3
        lcr = {"type": "LCR",
                "network":self.device['network'],
                "data":{
                    "id": str(uuid.uuid4()),
                    "timeout": self.config.get('LCR', 'timeout'),
                    "keepAwake":self._keepAwake,
                    "devType": self.device['DTY'],
                    "toQuery": query
                    }
                    }
        if self.device['setENC']:
            print("adding setENC to lcr")
            lcr['data']['setENC'] = 1
        self._lastLCR.append(lcr)
        self._sendRequest(lcr)

    def _entryAppend(self, query, command, value):
        """
            The following are use to append the correct LLAP commands
            to the passed query and return the altered query
            based on the type of Entry
            
        """
        if value[2] == 'String':
            query.append(
                         {'command': command,
                          'value': value[0].get()
                         }
                         )
        elif value[2] == 'Float':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'Int':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'ONOFF':
            if value[0].get() == 1:
                query.append({'command': command, 'value': "ON"})
            else:
                query.append({'command': command, 'value': "OFF"})

        elif value[2] == 'ONOFFTOG':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'ID':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'Hex':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'ReadOnlyHex':
            pass
        elif value[2] == 'Period':
            query.append(
                         {'command': command,
                         'value': value[0].get()
                         }
                         )
        elif value[2] == 'SleepMode':
            if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
                query.append({'command': "SLEEPM",
                             'value': ("16" if self.entry['SLEEPM'][0].get() else "0")
                             }
                             )
            elif self.devices[self.device['id']]['SleepMode'] == "Interrupt":
                query.append({'command': "SLEEPM",
                             'value': ("8" if self.entry['SLEEPM'][0].get() else "0")
                             }
                             )
        elif value[2] == 'ENKey':
            # set encryption key
            # need to split into each EN[1-6]
            # Test keys
            #      ><    ><    ><    ><    ><>
            # 12345678901234567890123456789012
            # A1B2C3D4E5F6A2B3C4DE6F7A3B4C5D6E
            #self.logger.debug("ENKEY Length: {}".format(len(self.entry['ENKEY'][0].get())))
            if len(value[0].get()) == 32:
                # key is long enough
                query.append({'command': "EN1", 'value': value[0].get()[0:6]})
                query.append({'command': "EN2", 'value': value[0].get()[6:12]})
                query.append({'command': "EN3", 'value': value[0].get()[12:18]})
                query.append({'command': "EN4", 'value': value[0].get()[18:24]})
                query.append({'command': "EN5", 'value': value[0].get()[24:30]})
                query.append({'command': "EN6", 'value': value[0].get()[30:32]})
                self.entry[command][0].set("") # clear encryption key box

        return query

    def _queryType(self):
        """ Time to send a query to see if we have a device in pair mode
            this is going to need time out's? possible retries
            devtype and apver request
        """
        self.logger.debug("Query type")
        self._checkServer = False
        # TODO: add a line here to disable NEXT button on pfame
        query = [
                 {'command': "DTY"},
                 {'command': "APVER"},
                 {'command': "CHDEVID"}
                ]
        self._configState = 1
        lcr = {"type": "LCR",
               "network":self._network,
               "data":{
                       "id": str(uuid.uuid4()),
                       "timeout": 30,   # short time out
                       "toQuery": query
                       }
              }
        
        self._lastLCR.append(lcr)
        self._sendRequest(lcr)
    
    def _processReply(self, json):
        self.logger.debug("Processing reply")
        # no longer waiting on a reply
        self.fWaitingForReply.clear()
        # split up the json
        reply = json['data']
        self.logger.debug("id: {}, devType:{}, Replies:{}".format(reply['id'],
                                                                  reply.get('devType', ""),
                                                                  reply['replies']))
        # check if reply is valid
        if reply['state'] == "FAIL_TIMEOUT":
            # TODO: handle failed due to timeout
            self.logger.debug("LCR timeout")
            # display pop up ask user to check configme mode and try again
            if tkMessageBox.askyesno("Communications Timeout",
                                     ("Please check the device is in CONFIGME mode and \n"
                                      "Click yes to retry\n"
                                      "No to return to pervious screen")
                                     ):
                # send query again
                self._sendRequest(self._lastLCR[-1])
            else:
                if self._currentFrame == "pressFrame":
                    self._startOver()
        elif reply['state'] == "FAIL_RETRY":
            # TODO: handle failed due to retry
            self.logger.debug("LCR retry error")
            # display pop up ask user to check configme mode and try again
            if tkMessageBox.askyesno("Communications Timeout",
                                     ("Please check the device is in CONFIGME mode and \n"
                                      "Click yes to retry\n"
                                      "No to return to pervious screen")
                                     ):
                # send query again
                self._sendRequest(self._lastLCR[-1])
            else:
                if self._currentFrame == "pressFrame":
                    self._startOver()
        elif reply['state'] == "PASS":
            # process reply
            if self._configState == 1:
                # this was a query type request
                if float(reply['replies']['APVER']['reply']) >= 2.0:
                    # valid apver
                    # so check what replied
                    for n in range(len(self.devices)):
                        if self.devices[n]['DTY'] == reply['replies']['DTY']['reply']:
                            # we have a match
                            self.logger.debug("Matched device")
                            self.device = {'id': n,
                                           'DTY': self.devices[n]['DTY'],   # copy form JSON not reply
                                           'devID': reply['replies']['CHDEVID']['reply'],
                                           'newDevice': False,
                                           'setENC': False,
                                           'settingsMissMatch': False,
                                           'network': json['network']
                                          }
                            self._askCurrentConfig()
                else:
                    # apver mismatch, show error screen
                    pass
            elif self._configState == 2:
                # this was an information request
                # populate fields
                self.device['newDevice'] = False
                if self.device['devID'] == '':
                    self.entry['CHDEVID'][0].set("--")
                else:
                    self.entry['CHDEVID'][0].set(self.device['devID'])
                    if self.device['devID'] == '??':
                        # this is a new or reset device, set a flag so we know later
                        self.device['newDevice'] = True
                for command, args in reply['replies'].items():
                    if command == "CHREMID" and args['reply'] == '':
                        self.entry[command][0].set("--")
                    elif command == "SLEEPM":
                        value = int(args['reply'])
                        if value != 0:
                            self.entry[command][0].set(1)
                        else:
                            self.entry[command][0].set(0)
                    elif command == "ENC":
                        if args['reply'] == "OFF":
                            self.entry[command][0].set(0)
                        elif args['reply'] == "ON":
                            self.entry[command][0].set(1)
                        else:
                            #should not get here
                            self.logger.debug("Error in reply to ENC")
                    elif command == "INTVL":
                        self.entry[command][0].set(args['reply'])
                    else:
                        if command in self.entry:
                            # TODO: need to handle check box entry (Format: ONOFF)
                            if self.entry[command][2] == 'Int':
                                self.entry[command][0].set(args['reply'])
                            else:
                                self.entry[command][0].set(args['reply'])

                # copy config so we can compare it later
                self._entryCopy()
                # new device setup
                if self.device['newDevice']:
                    self._newDeviceAutoSetup()
                else:
                    if self.entry['PANID'][0].get() != self._servers[self._network]['data']['result']['PANID']:
                        self.device['settingsMissMatch'] = True
                    if self.entry['ENC'][0].get() != self._servers[self._network]['data']['result']['encryptionSet']:
                        self.device['settingsMissMatch'] = True
                    
                # show config screen
                self.logger.debug("Setting keepAwake, display config")
                # TODO: set keepAwake via UDP LCR
                self._keepAwake = 1
                self._displaySimpleConfig()
            elif self._configState == 3:
                # this was a config request
                # TODO: check replies were good and let user know device is now ready
                enkeyCount = 0
                enkeyMatch = 0
                en = re.compile('^EN[1-6]')

                for command, arg in reply['replies'].items():
                    if en.match(command):
                        enkeyCount += 1
                        if arg['reply'] == "ENACK":
                            enkeyMatch += 1
                    elif arg['value'] != arg['reply']:
                        # values don't match we should warn user
                        tkMessageBox.showerror("Value mismatch",
                                               "The {} value was not set, \n Sent: {}\n Got back: {}".format(command, arg['value'], arg['reply']))

                if enkeyCount != 0 and enkeyMatch != 6:
                    # encryption key not fully set
                    tkMessageBox.showerror("Encryption Key Error",
                                           "Your encryption key was not correctly set please try again")

                # show end screen
                self._displayEnd()
            elif self._configState == 4:
                pass
            elif self._configState == 5:
                # have done a reset so should get back factory settings
                # check dev id is now ?? and update local
                self.device['devID'] = reply['replies']['CHDEVID']['reply']
                if self.device['devID'] == "??":
                    self._askCurrentConfig()
                else:
                    # TODO: LLAPRESET didn't work ERROR
                    pass
        # TODO: clean up
        
    def _askCurrentConfig(self):
        # assuming we know what it is ask for the current config
        self.logger.debug("Ask current config")
        self._requestServerDetails(self._network)
        self.pframe.children['pressText'].config(text=PRESSTEXT1)
        query = [
                 {'command': "PANID"},
                 {'command': "RETRIES"},
                 {'command': "SNL"},
                 {'command': "SNH"},
                 {'command': "ENC"},
                 {'command': "RSSI"}
                 ]
        
        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
            query.append({'command': "INTVL"})
            query.append({'command': "WAKEC"})
            query.append({'command': "SLEEPM"})
        elif self.devices[self.device['id']]['SleepMode'] == "Interrupt":
            query.append({'command': "SLEEPM"})
        
        for n in self.devices[self.device['id']]['Options']:
            # create place to put the reply later
            self.entry[n['Command']] = [tk.StringVar(), tk.StringVar(), 'String']
            query.append({'command': n['Command'].encode('ascii', 'ignore')})
        
        
        self.logger.debug("Setting keepAwake")
        self._keepAwake = 1
        
        self._configState = 2
        lcr = {"type": "LCR",
                "network":self.device['network'],
                "data":{
                    "id": str(uuid.uuid4()),
                    "timeout": 60,
                    "keepAwake":self._keepAwake,
                    "devType": self.device['DTY'],
                    "toQuery": query
                    }
                }
    
        self._lastLCR.append(lcr)
        self._sendRequest(lcr)

    def _newDeviceAutoSetup(self):
        # double check
        if self.device['newDevice']:
            # give it a new deviceID
            self.entry['CHDEVID'][0].set(self._getNextFreeID())
            try:
                if self.entry['PANID'][0].get() != self._servers[self._network]['data']['result']['PANID']:
                    self.entry['PANID'][0].set(self._servers[self._network]['data']['result']['PANID'])
                if self.entry['ENC'][0].get() != self._servers[self._network]['data']['result']['encryptionSet']:
                    if self._servers[self._network]['data']['result']['encryptionSet']:
                        self.device['setENC'] = True
                    else:
                        self.device['setENC'] = False
            except:
                pass




    def _requestServerDetails(self, network):
        self.logger.debug("Ask server {} for its deviceStore".format(network))
        serverQuery = {
                       "type": "Server",
                       "network": network,
                       "data":{
                           "id": str(uuid.uuid4()),
                           "request": [
                                       "deviceStore",
                                       "PANID",
                                       "encryptionSet"
                                       ]
                       }
                      }
        self._sendRequest(serverQuery)

    def _updateServerDetailsFromJSON(self, jsonin):
        # update server entry in our list
        # TODO: this needs to be a intelligent merge not just overwrite
        if jsonin['network'] in self._servers.keys():
            network = jsonin['network']
            self._servers[network]['state'] = jsonin.get('state', "Unknown")
            self._servers[network]['timestamp'] = jsonin['timestamp']
            if jsonin.has_key('data'):
                if not self._servers[network].has_key('data'):
                    self._servers[network]['data'] = jsonin['data']
                else:
                    if jsonin.has_key('id'):
                        self._servers[network]['data']['id'] = jsonin['data']['id']
                    if jsonin.has_key('result'):
                        results = jsonin['data']['result']
                        if not self._servers[network]['data'].has_key('result'):
                            self._servers[network]['data']['result'] = results
                        else:
                            if results.has_key('PAINID'):
                                self._servers[network]['data']['result']['PANID'] = results['PANID']
                            if results.has_key('encryptionState'):
                                self._servers[network]['data']['result']['encryptionSet'] = results['encryptionSet']
                            if results.has_key('deviceStore'):
                                self._servers[network]['data']['result']['deviceStore'] = results['deviceStore']
        else:
            # new entry store the whole packet
            self._servers[jsonin['network']] = jsonin
        self.fServerUpdate.set()


    def _processNoReply(self):
        self.logger.debug("No Reply with in timeouts")
        # ask user to press pair button and try again?
        
        if tkMessageBox.askyesno("Communications Timeout",
                                 ("No replay from the Server, \n"
                                  "To try again \n"
                                  "click yes"
                                  )
                                 ):
            self._displayProgress()
            self._starttime = time()
            self._replyCheck()
        else:
            # TODO: we need to cancel the LCR with the core
            # TODO: UDP JSON has no cancel but it will time out
            #            self._lcm.cancelLCR()
            if self._currentFrame == "pressFrame":
                self._startOver
            
    def _sendRequest(self, lcr):
        self.logger.debug("Sending Request to LCMC")
        self._displayProgress()
        self._starttime = time()
        self.fWaitingForReply.set()
        self.qUDPSend.put(json.dumps(lcr))
        self._replyCheck()
    
    def _replyCheck(self):
        # look for a reply
        # TODO: wait on UDP reply (how long)
        if self.fWaitingForReply.is_set():
            if self.qLCRReply.empty():
                if time()-self._starttime > int(self._lastLCR[-1]['data']['timeout'])+10:
                    # if timeout passed, let user know no reply
                    # close wait diag
                    if self._currentFrame != "pressFrame":
                        try:
                            self.progressWindow.destroy()
                        except:
                            pass
                        self.master.children[self._currentFrame].children['next'].config(state=tk.ACTIVE)
                    self._processNoReply()
                else:
                    # update wait diag and check again
                    self.master.after(500, self._replyCheck)
            else:
                json = self.qLCRReply.get()
                # check reply ID with Expected ID
                if json['data']['id'] != self._lastLCR[-1]['data']['id']:
                    # added this to cope with receiving multiple replies
                    # e.g. if there are multiple network interfaces active
                    self.master.after(500, self._replyCheck)
                else:
                    self.logger.debug("reply is expected ID: {}".format(json['data']['id']))
                    # close wait diag and return reply
                    if self._currentFrame != "pressFrame":
                        try:
                            self.progressWindow.destroy()
                        except:
                            pass
                        if self._currentFrame is not "pressFrame" and self._currentFrame is not "introFrame":
                            self.master.children[self._currentFrame].children['next'].config(state=tk.ACTIVE)
                    self._processReply(json)
                self.qLCRReply.task_done()
    
    def _buildGrid(self, frame, quit=False, halfSize=False):
        self.logger.debug("Building Grid for {}".format(frame.winfo_name()))
        canvas = tk.Canvas(frame, bd=0, width=self._widthMain-4,
                               height=self._rowHeight, highlightthickness=0)
        canvas.grid(row=0, column=0, columnspan=6)
        
        if halfSize:
            rows=self._rows/2
        else:
            rows=self._rows
        for r in range(rows):
            for c in range(6):
                tk.Canvas(frame, bd=0, #bg=("black" if r%2 and c%2 else "gray"),
                          highlightthickness=0,
                          width=(self._widthMain-4)/6,
                          height=self._rowHeight
                          ).grid(row=r, column=c)
        if (quit):
            tk.Button(frame, text='Quit', command=self._endConfigMe
                      ).grid(row=rows-2, column=0, sticky=tk.E)

    # TODO: UDP JSON debug window
    def _jsonWindowDebug(self):
        self.logger.debug("Setting up JSON debug window")
        self.serialWindow = tk.Toplevel(self.master)
        self.serialWindow.geometry(
               "{}x{}+{}+{}".format(self._widthSerial,
                                    self._heightSerial,
                                    int(self.config.get('LLAPCM',
                                                        'window_width_offset')
                                        )+self._widthMain+20,
                                    self.config.get('LLAPCM',
                                                    'window_height_offset')
                                    )
                                   )
        self.serialWindow.title("LLAP Config Me JSON Debug")
    
        self.serialDebugText = tk.Text(self.serialWindow, state=tk.DISABLED,
                                       relief=tk.RAISED, borderwidth=2,
                                       )
        self.serialDebugText.pack()
        self.serialDebugText.tag_config('TX', foreground='red')
        self.serialDebugText.tag_config('RX', foreground='blue')
        self._serialDebugUpdate()
    
    def _serialDebugUpdate(self):
        # TODO: nice formation for JSON's?
        if not self.qJSONDebug.empty():
            txt = self.qJSONDebug.get()
            self.serialDebugText.config(state=tk.NORMAL)
            self.serialDebugText.insert(tk.END, txt[0]+"\n", txt[1])
            self.serialDebugText.see(tk.END)
            self.serialDebugText.config(state=tk.DISABLED)
            self.qJSONDebug.task_done()
        
        self.master.after(2, self._serialDebugUpdate)
    
    def _endConfigMe(self):
        self.logger.debug("End Client")
        position = self.master.geometry().split("+")
        self.config.set('LLAPCM', 'window_width_offset', position[1])
        self.config.set('LLAPCM', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def _cleanUp(self):
        self.logger.debug("Clean up and exit")
        # if we were talking to a device we should send a CONFIGEND
        # TODO: send JSON in stead
        
        self._stopKeepAwake()
    
        # cancel anything outstanding
        # TODO: we have no cancel, we have time outs
        # self._lcm.cancelLCR()
        # disconnect resources
        # TODO: close sockets
        # self._lcm.disconnect_transport()
        self._writeConfig()
        try:
            self.tUDPSendStop.set()
            self.tUDPSend.join()
        except:
            pass
        try:
            self.tUDPListenStop.set()
            self.tUDPListen.join()
        except:
            pass

    def _stopKeepAwake(self):
        if self._keepAwake:
            self.logger.debug("Stopping keepAwake")
            self._keepAwake = 0
            query = [{'command': "CONFIGEND"}]
            self._configState = 4
            lcr = {"type": "LCR",
                    "network":self.device['network'],
                    "data":{
                        "id": str(uuid.uuid4()),
                        "keepAwake":self._keepAwake,
                        "timeout": 30,                  # short time out on this one
                        "devType": self.device['DTY'],
                        "toQuery": query
                        }
                    }
            self.logger.debug("Sending ConfigEnd LCR")
            self._starttime = time()
            self.qUDPSend.put(json.dumps(lcr))
            while self.qLCRReply.empty() and time()-self._starttime < 5:
                sleep(0.1)

    def _checkArgs(self):
        self.logger.debug("Parse Args")
        parser = argparse.ArgumentParser(description='LLAP Config Me Client')
        parser.add_argument('-d', '--debug',
                            help='Enable debug output to console, overrides LAPCM.cfg setting',
                            action='store_true')
        parser.add_argument('-l', '--log',
                            help='Override the debug logging level, DEBUG, INFO, WARNING, ERROR, CRITICAL'
                            )
        
        self.args = parser.parse_args()

    def _readConfig(self):
        self.logger.debug("Reading Config")
        
        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self._configFileDefault))
        except:
            self.logger.debug("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self._configFile):
            self.logger.debug("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self.logger.debug("No Config Loaded, Quitting")
            sys.exit()


    def _writeConfig(self):
        self.logger.debug("Writing Config")
        with open(self._configFile, 'wb') as _configFile:
            self.config.write(_configFile)

    def _loadDevices(self):
        self.logger.debug("Loading device List")
        try:
            with open(self.config.get('LLAPCM', 'devFile'), 'r') as f:
                read_data = f.read()
            f.closed
            
            # TODO: Check/catch json errors
            self._llapGenericCommands = json.loads(read_data)['Generic Commands']
            self._llapCyclicCommands = json.loads(read_data)['Cyclic Commands']
            self._readingPeriods = json.loads(read_data)['Reading Periods']
            self.devices = json.loads(read_data)['Devices']
    
        except IOError:
            self.logger.debug("Could Not Load DevList File")
            self.devices = [
                            {'id': 0,
                             'Description': 'Error loading DevList file'
                            }]

#    def die(self):
#        """For some reason we can not longer go forward
#            Try cleaning up what we can and exit
#        """
#        self.logger.critical("DIE")
##        self._endConfigMe()
#        self._cleanUp()
#
#        sys.exit(1)

if __name__ == "__main__":
    app = LLAPCongfigMeClient()
    app.on_excute()