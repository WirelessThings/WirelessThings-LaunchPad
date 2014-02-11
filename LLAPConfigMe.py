#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAP ConfigMe
    Copyright (c) 2013 Ciseco Ltd.
    
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
import serial
import json
import ConfigParser
import tkMessageBox
import threading
import Queue
from time import sleep, asctime, time
#import ImageTk
from LLAPConfigMeCore import *


if sys.platform == 'darwin':
    port = '/dev/tty.usbmodem000001'
elif sys.platform == 'win32':
    port = ''
else:
    port = '/dev/ttyAMA0'

INTRO = """Welcome to LLAP Config me wizard
Please enter your com port below to continue"""

PAIR = """Please press the Config Me button on your device and click next"""

CONFIG = """Selet your device config options"""

END = """Your device has been configured"""


class LLAPCongfigMeClient:
    """
        LLAP ConfigMe Client Class
        Handels display of wizzard interface for configuring devices
        pass reuestes onto LLAPConfigMeCore
    """
    _debug = False # until we read config
    _debugArg = False # or get command line
    _configFileDefault = "LLAPCM_defaults.cfg"
    _configFile = "LLAPCM.cfg"
    _devFile = "LLAPDevices.json"
    _myNodesFile = "MyNodes.json"
    
    _rows = 19
    _rowHeight = 28
    _widthMain = 604
    _heightMain = (_rows*_rowHeight)+4
    _widthSerial = 400
    _heightSerial = 200
    
    # how long to wait for a reply before asking user to press button again in seconds
    _timeout = 60
    _devIDInputs = []

    def __init__(self):
        """
            setup variables
        """
        self._lcm = LLAPConfigMeCore()
        
        self._running = False

    def on_excute(self):
        """
            entry point for running
        """
        self._checkArgs()
        self._readConfig()
        self._loadDevices()

        if self.args.mqtt:
            self._lcm.set_mode(MQTT)

        if self._debugArg or self._debug:
            self._lcm.debug = True
        
        self._running = True

        # run the GUI's
        self._runConfigMe()
        self._cleanUp()

    def _runConfigMe(self):
        self._debugPrint("Running Main GUI")
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

        self.master.title("LLAP Config Me v{}".format(self.currentVersion))
        self.master.resizable(0,0)
        
        self._initTkVariables()
        self._initValidationRules()
        
        if self._debugArg or self._debug:
            self._serialDebug()

        self._displayIntro()
        
        self.master.mainloop()

    def _initTkVariables(self):
        self._debugPrint("Init Tk Variables")
        
        self.comport = tk.StringVar()
        self.comport.set(port)
    
        if self.args.mqtt:
            self.comport.set('localhost')
        
        self.entry = {
                      "CHDEVID" : tk.StringVar(),
                      "PANID" : tk.StringVar(),
                      "RETRIES" : tk.StringVar(),
                      "INTVL" : tk.StringVar(),
                      "WAKEC" : tk.StringVar(),
                      "SLEEPM" : tk.IntVar()
                     }
    
    def _displayIntro(self):
        self._debugPrint("Display Intro Page")
        self.iframe = tk.Frame(self.master, name='introFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.iframe.pack()
        
        self._buildGrid(self.iframe)
        
        tk.Label(self.iframe, text=INTRO).grid(row=1, column=0, columnspan=6,
                                               rowspan=self._rows-4)
        # com selection bits
        tk.Label(self.iframe, text='Com Port').grid(row=self._rows-4,
                                                    column=2, columnspan=2)
        tk.Entry(self.iframe, textvariable=self.comport, width=20
                 ).grid(row=self._rows-3, column=2, columnspan=2)



        tk.Button(self.iframe, text='Back', state=tk.DISABLED
                  ).grid(row=self._rows-2, column=4, sticky=tk.E)
        tk.Button(self.iframe, text='Next', command=self._displayPair
                  ).grid(row=self._rows-2, column=5, sticky=tk.W)
                   
    def _displayPair(self):
        self._debugPrint("Connecting and Displaying Pair window")
        
        if self._connect():
            self.iframe.pack_forget()

            self.pframe = tk.Frame(self.master, name='pairFrame', relief=tk.RAISED,
                                   borderwidth=2, width=self._widthMain,
                                   height=self._heightMain)
            self.pframe.pack()
        
            self._buildGrid(self.pframe)

            tk.Label(self.pframe, text=PAIR).grid(row=1, column=0, columnspan=6,
                                                  rowspan=self._rows-4)
        
            tk.Button(self.pframe, text='Back', state=tk.DISABLED
                      ).grid(row=self._rows-2, column=4, sticky=tk.E)
            tk.Button(self.pframe, text='Next', command=self._queryType
                      ).grid(row=self._rows-2, column=5, sticky=tk.W)
                
    def _displayConfig(self):
        self._debugPrint("Displaying Decive type based config screen")
        self.pframe.pack_forget()
                
        self.cframe = tk.Frame(self.master, name='configFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.cframe.pack()

        self._buildGrid(self.cframe)

        tk.Label(self.cframe, text=CONFIG).grid(row=0, column=0, columnspan=6)
        
        # generic config options
        tk.Label(self.cframe, text="Generic Commands"
                 ).grid(row=1, column=0, columnspan=3)
                 
        tk.Label(self.cframe, text="Device ID").grid(row=2, column=0, columnspan=3)
        tk.Label(self.cframe, text="CHDEVID").grid(row=3, column=0, sticky=tk.E)
        self._devIDInputs.append(tk.Entry(self.cframe, textvariable=self.entry['CHDEVID'], width=20,
                                         validate='key',
                                         invalidcommand='bell',
                                         validatecommand=self.vDevID,
                                         name='chdevid'
                                         )
                                )
        self._devIDInputs[-1].grid(row=3, column=1, columnspan=2, sticky=tk.W)
                 
        tk.Label(self.cframe, text="Pan ID").grid(row=4, column=0, columnspan=3)
        tk.Label(self.cframe, text="PANID").grid(row=5, column=0, sticky=tk.E)
        tk.Entry(self.cframe, textvariable=self.entry['PANID'], width=20,
                 validate='key',
                 invalidcommand='bell',
                 validatecommand=self.vUpper,
                 ).grid(row=5, column=1, columnspan=2, sticky=tk.W)
         
        tk.Label(self.cframe, text="Retries for Announcements"
                 ).grid(row=6, column=0, columnspan=3)
        tk.Label(self.cframe, text="RETRIES").grid(row=7, column=0, sticky=tk.E)
        tk.Entry(self.cframe, textvariable=self.entry['RETRIES'], width=20
                 ).grid(row=7, column=1, columnspan=2, sticky=tk.W)
        
        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
            # cyclic config options
            tk.Label(self.cframe, text="Cyclic Commands"
                     ).grid(row=9, column=0, columnspan=3)
            tk.Label(self.cframe, text="Sleep Interval"
                     ).grid(row=10, column=0, columnspan=3)
            tk.Label(self.cframe, text="INTVL").grid(row=11, column=0, sticky=tk.E)
            tk.Entry(self.cframe, textvariable=self.entry['INTVL'], width=20,
                     validate='key',
                     invalidcommand='bell',
                     validatecommand=self.vUpper,
                    ).grid(row=11, column=1, columnspan=2, sticky=tk.W)
    
            tk.Label(self.cframe, text="Battery Wake Count"
                     ).grid(row=12, column=0, columnspan=3)
            tk.Label(self.cframe, text="WAKEC").grid(row=13, column=0, sticky=tk.E)
            tk.Entry(self.cframe, textvariable=self.entry['WAKEC'], width=20,
                    ).grid(row=13, column=1, columnspan=2, sticky=tk.W)
        
            tk.Label(self.cframe, text="Enable Cyclic Sleep"
                     ).grid(row=14, column=0, columnspan=3)
            tk.Label(self.cframe, text="CYCLE").grid(row=15, column=0, sticky=tk.E)
            tk.Checkbutton(self.cframe, variable=self.entry['SLEEPM']
                          ).grid(row=15, column=1, columnspan=2, sticky=tk.W)
        elif self.devices[sellf.device['id']]['SleepMode'] == "Cyclic":
            # Interupt sleep decivces
            tk.Label(self.cframe, text="Interupt Sleep"
                     ).grid(row=9, column=0, columnspan=3)
            tk.Label(self.cframe, text="SLEEP").grid(row=10, column=0, sticky=tk.E)
            tk.Checkbutton(self.cframe, variable=self.entry['SLEEPM']
                          ).grid(row=10, column=1, columnspan=2, sticky=tk.W)
        
        # device config options
        tk.Label(self.cframe,
                 text="{} Options".format(self.devices[self.device['id']]['Name'])
                 ).grid(row=1, column=3, columnspan=3)
        r = 0
        for n in self.devices[self.device['id']]['Options']:
            
            tk.Label(self.cframe, text=n['Description']
                     ).grid(row=2+r, column=3, columnspan=3)
            tk.Label(self.cframe, text=n['Command']
                     ).grid(row=3+r, column=3, sticky=tk.E)
            if n['Format'] == "ONOFF":
                e = tk.Checkbutton(self.cframe, variable=self.entry[n['Command']],
                                   onvalue="ON", offvalue="OFF",
                                   name=n['Command'].lower()
                                   )
                e.grid(row=3+r, column=4, columnspan=2, sticky=tk.W)
            else:
                e = tk.Entry(self.cframe, textvariable=self.entry[n['Command']],
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
                    
            r += 2
        
        # buttons
        tk.Button(self.cframe, text='Back', state=tk.DISABLED
                  ).grid(row=self._rows-2, column=4, sticky=tk.E)
        tk.Button(self.cframe, text='Next', command=self._sendConfigRequest
                  ).grid(row=self._rows-2, column=5, sticky=tk.W)

    def _displayEnd(self):
        self._debugPrint("Displying end screen")
    
        self.cframe.pack_forget()

        self.eframe = tk.Frame(self.master, name='endFrame', relief=tk.RAISED,
                               borderwidth=2, width=self._widthMain,
                               height=self._heightMain)
        self.eframe.pack()
        
        self._buildGrid(self.eframe)
        
        tk.Label(self.eframe, text=END).grid(row=1, column=0, columnspan=6,
                                              rowspan=self._rows-4)
                                              
        tk.Button(self.eframe, text='Back', state=tk.DISABLED
                ).grid(row=self._rows-2, column=4, sticky=tk.E)
        tk.Button(self.eframe, text='Start Over', command=self._startOver
                  ).grid(row=self._rows-2, column=5, sticky=tk.W)

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
        self._debugPrint("Setting up GUI validation Rules")
        self.vUpper = (self.master.register(self.validUpper), '%d', '%P', '%S')
        self.vDevID = (self.master.register(self.validDevID), '%d',
                       '%P', '%W', '%P', '%S')
        self.vInt = (self.master.register(self.validInt), '%d', '%s', '%S')
    
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

    def validDevID(self, d, P, W, s, S):
        valid = False
        validChar = ['#', '@', '\\', '*'] # as of llap 2.0 - and ? cannot be set
        for c in validChar:
            if S.startswith(c):
                valid = True
        
        if d == '0' or d == '-1':
            return True
        elif S.islower() and (len(P) <= 2):
            self.entry[W.split('.')[-1].upper()].set(P.upper())
            self.master.after_idle(self.vdevSet)
        elif (S.isupper() or valid) and (len(P) <= 2):
            return True
        else:
            return False
    
    def vdevSet(self):
        for e in self._devIDInputs:
            e.icursor(e.index(tk.INSERT)+1)
            e.config(validate='key')
    
    def _startOver(self):
        self._debugPrint("Starting over")
        self.eframe.pack_forget()
        self.pframe.pack()

    def _displayProgress(self):
        self._debugPrint("Displaying progress pop up")
        
        position = self.master.geometry().split("+")
        
        self.progressWindow = tk.Toplevel()
        self.progressWindow.geometry("+{}+{}".format(
                                             int(position[1])+self._widthMain/4,
                                             int(position[2])+self._heightMain/4
                                                     )
                                     )
            
        self.progressWindow.title("Working")

        tk.Label(self.progressWindow,
                 text="Comunicating with device please wait").pack()

        self.progressBar = ttk.Progressbar(self.progressWindow,
                                           orient="horizontal", length=200,
                                           mode="indeterminate")
        self.progressBar.pack()
        self.progressBar.start()
    
    def _sendConfigRequest(self):
        self._debugPrint("Sending config request to device")

        # build config query from values in entry
        # generic commands first
        query = [
                 "CHDEVID{}".format(self.entry['CHDEVID'].get()),
                 "PANID{}".format(self.entry['PANID'].get()),
                 "RETRIES{}".format(self.entry['RETRIES'].get())
                ]
                
        # device specfic commands next
        for n in self.devices[self.device['id']]['Options']:
            query.append("{}{}".format(n['Command'],
                                       self.entry[n['Command']].get()))
        
        # cyclic stuff last (cycle acts as save and exit)       
        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
            query.append("INTVL{}".format(self.entry['INTVL'].get()))
            query.append("WAKEC{}".format(self.entry['WAKEC'].get()))
            query.append("SLEEPM{}".format((16 if self.entry['SLEEPM'].get() else 0)))
        elif slef.devices[self.device['id']]['SleepMode'] == "Interput":
            query.append("SLEEPM{}".format((8 if self.entry['SLEEPM'].get() else 0)))
        else:
            # append save and exits command?
            pass
        # always finish with reboot to save and apply
        query.append("REBOOT")

        lcr = LLAPConfigRequest(id=3,
                                devType=self.device['DTY'],
                                toQuery=query
                                )

        self._sendRequest(lcr)

    def _queryType(self):
        """ Time to send a query to see if we have a device in pair mode
            this is going to need time out's? posible retries
            devtype and apver request
        """
        self._debugPrint("Query type")
        # TODO: add a line here to disable NEXT button on pfame
        query = ["DTY", "APVER", "CHDEVID"]
        lcr = LLAPConfigRequest(id=1, toQuery=query)

        self._sendRequest(lcr)
    
    def _processReply(self):
        self._debugPrint("Processing reply")
        reply = self._lcm.replyQ.get()
        self._debugPrint("id: {}, devType:{}, Replies:{}".format(reply.id,
                                                                reply.devType,
                                                                reply.replies))
        if reply.id == 1:
            # this was a query type request
            if float(reply.replies[1][1][5:]) >= 2.0:
                # valid apver
                # so check what replied
                for n in range(len(self.devices)):
                    if self.devices[n]['DTY'] == reply.replies[0][1]:
                        # we have a match
                        self.device = {'id': n,
                                       'DTY': self.devices[n]['DTY'],
                                       'devID': reply.replies[2][1][7:]
                                      }
                        # assuming we know what it is ask for the current config
                        query = ["PANID", "RETRIES"]
                        
                        if self.devices[self.device['id']]['SleepMode'] == "Cyclic":
                            query.append("INTVL")
                            query.append("WAKEC")
                            query.append("SLEEPM")
                        elif self.devices[self.defice['id']]['SleepMode'] == "Interupt":
                            query.append("SLEEPM")
                        
                        for n in self.devices[self.device['id']]['Options']:
                            # create place to put the reply later
                            self.entry[n['Command']] = tk.StringVar()
                            query.append(n['Command'].encode('ascii', 'ignore'))

                        lcr = LLAPConfigRequest(id=2,
                                                    devType=self.device['DTY'],
                                                toQuery=query
                                                )

                        self._sendRequest(lcr)
                        
            else:
                # apver mismatch, show error screen
                pass
        elif reply.id == 2:
            # this was an information request
            # populate fields
            if self.device['devID'] == '':
                self.entry['CHDEVID'].set("--")
            else:
                self.entry['CHDEVID'].set(self.device['devID'])
                
            for e in reply.replies:
                if e[0] == "CHREMID" and e[1][len(e[0]):] == '':
                    self.entry[e[0]].set("--")
                elif e[0] == "SLEEPM":
                    value = int(e[1][len(e[0]):])
                    if value != 0:
                        self.entry[e[0]].set(1)
                    else:
                        self.entry[e[0]].set(0)
                else:
                    if e[0] in self.entry:
                        self.entry[e[0]].set(e[1][len(e[0]):])
        
            # show config screen
            self._debugPrint("Setting keepAwake")
            self._lcm.keepAwake = True
            self._displayConfig()
            
        elif reply.id == 3:
            # this was a config request
            # check replies were good and let user know device is now ready
            
            # show end screen
            self._displayEnd()
        elif reply.id == 4:
            pass
        
        self._lcm.replyQ.task_done()

    def _processNoReply(self):
        self._debugPrint("No Reply with in timeouts")
        # ask user to press pair button and try again?
        if tkMessageBox.askyesno("Comunications Timeout", ("Unable to connect to device, \n"
                                                           "To try again check the deivce power,\n"
                                                           "press the ConfigMe button and click yes")
                                 ):
            self._displayProgress()
            self._starttime = time()
            self._replyCheck()
    
    def _sendRequest(self, lcr):
        self._debugPrint("Sending Reueset to LCMC")
        self._displayProgress()
        if self._lcm.keepAwake:
            self._debugPrint("Stopping keepAwake")
            self._lcm.keepAwake = False
        self._starttime = time()
        self._lcm.requestQ.put(lcr)
        self._replyCheck()
    
    def _replyCheck(self):
        # look for a reply
        if self._lcm.replyQ.empty():
            if time()-self._starttime > self._timeout:
                # if timeout passed, let user know no reply
                # close wait diag
                self.progressWindow.destroy()
                self._processNoReply()
            else:
                # update wait diag and check again
                self.master.after(500, self._replyCheck)
        else:
            # close wait diag and return reply
            self.progressWindow.destroy()
            self._processReply()
    
    def _buildGrid(self, frame):
        self._debugPrint("Building Grid for {}".format(frame.winfo_name()))
        canvas = tk.Canvas(frame, bd=0, width=self._widthMain-4,
                               height=self._rowHeight, highlightthickness=0)
        canvas.grid(row=0, column=0, columnspan=6)
        
        for r in range(self._rows):
            for c in range(6):
                tk.Canvas(frame, bd=0, #bg=("black" if r%2 and c%2 else "gray"),
                          highlightthickness=0,
                          width=(self._widthMain-4)/6,
                          height=self._rowHeight
                          ).grid(row=r, column=c)
    
        tk.Button(frame, text='Quit', command=self._endConfigMe
                  ).grid(row=self._rows-2, column=0, sticky=tk.E)

    def _connect(self):
        self._debugPrint("Connecting Serial port")
        self._lcm.set_baud(self.config.get('Serial', 'baudrate'))
        self._lcm.set_port(self.comport.get())
        
        # wrap this in a try block and throw a dialog window and return False
        self._lcm.connect_transport()
        if self._debugArg or self._debug:
            self._serialDebugUpdate()
        
        return True

    def _serialDebug(self):
        self._debugPrint("Setting up Serial debug window")
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
        self.serialWindow.title("LLAP Config Me Serial Debug")
    
        self.serialDebugText = tk.Text(self.serialWindow, state=tk.DISABLED,
                                       relief=tk.RAISED, borderwidth=2,
                                       )
        self.serialDebugText.pack()
        self.serialDebugText.tag_config('TX', foreground='red')
        self.serialDebugText.tag_config('RX', foreground='blue')
    
    def _serialDebugUpdate(self):
        if not self._lcm.transportQ.empty():
            txt = self._lcm.transportQ.get()
            self.serialDebugText.config(state=tk.NORMAL)
            self.serialDebugText.insert(tk.END, txt[0], txt[1])
            self.serialDebugText.see(tk.END)
            self.serialDebugText.config(state=tk.DISABLED)
            self._lcm.transportQ.task_done()
        
        self.master.after(10, self._serialDebugUpdate)
    
    def _endConfigMe(self):
        self._debugPrint("End Client")
        position = self.master.geometry().split("+")
        self.config.set('LLAPCM', 'window_width_offset', position[1])
        self.config.set('LLAPCM', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def _cleanUp(self):
        self._debugPrint("Clean up and exit")
        # if we were talking to a device we should send a CONFIGEND
        if self._lcm.keepAwake:
            query = ["CONFIGEND"]
            lcr = LLAPConfigRequest(id=4,
                                    devType=self.device['DTY'],
                                    toQuery=query
                                    )
                                    
            self._debugPrint("Sending ConfigEnd LCMC")
            if self._lcm.keepAwake:
                self._debugPrint("Stopping keepAwake")
                self._lcm.keepAwake = False
            self._starttime = time()
            self._lcm.requestQ.put(lcr)
            while self._lcm.replyQ.empty() and time()-self._starttime < 15:
                sleep(0.1)
    

        # disconnect resources
        self._lcm.disconnect_transport()
        self._writeConfig()
        
    def _debugPrint(self, msg):
        if self._debugArg or self._debug:
            print(msg)
    
    def _checkArgs(self):
        self._debugPrint("Parse Args")
        parser = argparse.ArgumentParser(description='LLAP Config Me Client')
        parser.add_argument('-d', '--debug',
                       help='Extra Debug Output, overrides LLAPCM.cfg setting',
                            action='store_true'
                            )
        parser.add_argument('-m', '--mqtt', help='Use MQTT for transport',
                            action='store_true'
                            )
                            
        
        self.args = parser.parse_args()
        
        if self.args.debug:
            self._debugArg = True
        else:
            self._debugArg = False

    def _readConfig(self):
        self._debugPrint("Reading Config")
        
        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self._configFileDefault))
        except:
            self._debugPrint("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self._configFile):
            self._debugPrint("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self._debugPrint("No Config Loaded, Quitting")
            sys.exit()
        
        self._debug = self.config.getboolean('Shared', 'debug')
        
        try:
            f = open(self.config.get('Shared', 'versionfile'))
            self.currentVersion = f.read()
            f.close()
        except:
            pass

    def _writeConfig(self):
        self._debugPrint("Writing Config")
        with open(self._configFile, 'wb') as _configFile:
            self.config.write(_configFile)

    def _loadDevices(self):
        self._debugPrint("Loading device List")
        try:
            with open(self._devFile, 'r') as f:
                read_data = f.read()
            f.closed
            
            self.devices = json.loads(read_data)['Devices']
    
        except IOError:
            self._debugPrint("Could Not Load DevList File")
            self.devices = [
                            {'id': 0,
                             'Description': 'Error loading DevList file'
                            }]




if __name__ == "__main__":
    app = LLAPCongfigMeClient()
    app.on_excute()