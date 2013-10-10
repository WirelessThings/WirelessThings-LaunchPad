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


class LLAPCongfigMeClient:
    """
        LLAP ConfigMe Client Class
        Handels display of wizzard interface for configuring devices
        pass reuestes onto LLAPConfigMeCore
    """

    def __init__(self):
        """
            setup variables
        """
        self.debug = False # until we read config
        self.debugArg = False # or get command line
        self.configFileDefault = "LLAPCM_defaults.cfg"
        self.configFile = "LLAPCM.cfg"
        self.devFile = "LLAPDevices.json"
        self.myNodesFile = "MyNodes.json"
        
        self.rows = 18
        self.widthMain = 754
        self.heightMain = (18*30)+4
        self.widthSerial = 400
        self.heightSerial = 200
        
        # how long to wait for a reply before asking user to press button again in seconds
        self.timeout = 60

        self.lcm = LLAPConfigMeCore()
        
        if self.debugArg or self.debug:
            self.lcm.debug = True
        
        self._running = False

    def on_excute(self):
        """
            entry point for running
        """
        self.checkArgs()
        self.readConfig()
        self.loadDevices()

        self._running = True

        # run the GUI's
        self.runConfigMe()

        self.cleanUp()

    def runConfigMe(self):
        self.debugPrint("Running Main GUI")
        self.master = tk.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self.endConfigMe)
        self.master.geometry(
                 "{}x{}+{}+{}".format(self.widthMain,
                                      self.heightMain,
                                      self.config.get('LLAPCM',
                                                      'window_width_offset'),
                                      self.config.get('LLAPCM',
                                                      'window_height_offset')
                                      )
                             )

        self.master.title("LLAP Config Me v{}".format(self.currentVersion))
        self.master.resizable(0,0)
        
        self.initTkVariables()
        
        if self.debugArg or self.debug:
            self.serialDebug()

        self.displayIntro()
        
        self.master.mainloop()

    def initTkVariables(self):
        self.debugPrint("Init Tk Variables")
        
        self.comport = tk.StringVar()
        self.comport.set(port)
    
    def displayIntro(self):
        self.debugPrint("Display Intro Page")
        self.iframe = tk.Frame(self.master, name='introFrame', relief=tk.RAISED,
                               borderwidth=2, width=self.widthMain,
                               height=self.heightMain)
        self.iframe.pack()
        
        self.buildGrid(self.iframe)

        # com selection bits
        tk.Label(self.iframe, text='Com Port').grid(row=self.rows-4,
                                                    column=2, columnspan=2)
        tk.Entry(self.iframe, textvariable=self.comport, width=20
                 ).grid(row=self.rows-3, column=2, columnspan=2)



        tk.Button(self.iframe, text='Back', state=tk.DISABLED
                  ).grid(row=self.rows-2, column=4, sticky=tk.E)
        tk.Button(self.iframe, text='Next', command=self.displayPair
                  ).grid(row=self.rows-2, column=5, sticky=tk.W)
                   
    def displayPair(self):
        self.debugPrint("Connecting and Displaying Pair window")
        
        if self.connect():
            self.iframe.pack_forget()

            self.pframe = tk.Frame(self.master, name='pairFrame', relief=tk.RAISED,
                                   borderwidth=2, width=self.widthMain,
                                   height=self.heightMain)
            self.pframe.pack()
        
            self.buildGrid(self.pframe)
        
            tk.Button(self.pframe, text='Back', state=tk.DISABLED
                      ).grid(row=self.rows-2, column=4, sticky=tk.E)
            tk.Button(self.pframe, text='Next', command=self.queryType
                      ).grid(row=self.rows-2, column=5, sticky=tk.W)

    def displayConfig(self):
        self.debugPrint("Displaying Decive type based config screen")
    
    def displayEnd(self):
        self.debugPring("Displying end screen")
    

    def queryType(self):
        """ Time to send a query to see if we have a device in pair mode
            this is going to need time out's? posible retries
            devtype and apver request
        """
        self.debugPrint("Query type")
        
        query = ["DEVTYPE", "APVER", "CHDEVID"]
        lcr = LLAPConfigRequest(toQuery=query)
    
        # start timer out (1min?)
        # while wait for reply
        # put resuest in que
        # should only take 5-10s seconds at most
        # poll replyQ,
        # should display a waiting sign?
        
        self.starttime = time()
        self.lcm.requestQ.put(query)
        self.replyCheck()
    
    def processReply(self):
        self.debugPrint("Processing reply")
        reply = self.lcm.replyQ.get()
    
        if reply.devType == None:
            # this was a query type request
            if float(reply.replies[1][1][5:]) >= 2.0:
                # valid apver
                # so check what replied
                for n in range(self.devices):
                    if n['DEVTYPE'] == reply.replies[0][1]:
                        # we have a match
                        self.device = {'id': n,
                                       'DEVTPYE': n['DEVTYPE'],
                                       'devID': reply.replies[2][1][7:]
                                      }
                        # assuming we know what it is ask it to stay awake a little longer
                        lcr = LLAPConfigRequest(devType=self.device['DEVTYPE'],
                                                toQuery=["AWAKE005M"]
                                                )
                        self.lcm.requestQ.put(lcr)
                        # show config screen
                        self.displayConfig(self)
            else:
                # apver mismatch, show error screen
        else:
            # this was a config request
            # check replies were good and let user know device is now ready
            
            # show end screen
            pass

    def processNoReply(self):
        self.debugPrint("No Reply with in timeouts")
        # ask user to press pair button and try again?
        
    
    def replyCheck(self):
        # look for a reply
        if self.lcm.replyQ.empty():
            if time()-self.starttime > self.timeout:
                # if timeout passed, let user know no reply
                # close wait diag
                self.processNoReply()
            else:
                # update wait diag and check again
                self.master.after(500, self.replyCheck)
        else:
            # close wait diag and return reply
            self.processReply()
    
    def buildGrid(self, frame):
        self.debugPrint("Building Grid for {}".format(frame.winfo_name()))
        canvas = tk.Canvas(frame, bd=0, width=self.widthMain-4,
                               height=30, highlightthickness=0)
        canvas.grid(row=0, column=0, columnspan=6)
        
        for r in range(self.rows):
            for c in range(6):
                tk.Canvas(frame, bd=0, bg=("black" if r%2 and c%2 else "gray"),
                          highlightthickness=0,
                          width=(self.widthMain-4)/6,
                          height=30
                          ).grid(row=r, column=c)
    
        tk.Button(self.iframe, text='Quit', command=self.endConfigMe
                  ).grid(row=self.rows-2, column=0, sticky=tk.E)

    def connect(self):
        self.debugPrint("Connecting Serial port")
        self.lcm.set_baud(self.config.get('Serial', 'baudrate'))
        self.lcm.set_port(self.comport.get())
        
        # wrap this in a try block and throw a dialog window and return False
        self.lcm.connect_transport()
        self.serialDebugUpdate()
        return True

    def serialDebug(self):
        self.debugPrint("Setting up Serial debug window")
        self.serialWindow = tk.Toplevel(self.master)
        self.serialWindow.geometry(
               "{}x{}+{}+{}".format(self.widthSerial,
                                    self.heightSerial,
                                    int(self.config.get('LLAPCM',
                                                    'window_width_offset'))+self.widthMain+20,
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
    
    def serialDebugUpdate(self):
        if not self.lcm.transportQ.empty():
            txt = self.lcm.transportQ.get()
            self.serialDebugText.config(state=tk.NORMAL)
            self.serialDebugText.insert(tk.END, txt[0], txt[1])
            self.serialDebugText.see(tk.END)
            self.serialDebugText.config(state=tk.DISABLED)
            self.lcm.transportQ.task_done()
        
        self.master.after(100, self.serialDebugUpdate)
    
    def endConfigMe(self):
        self.debugPrint("End Launcher")
        position = self.master.geometry().split("+")
        self.config.set('LLAPCM', 'window_width_offset', position[1])
        self.config.set('LLAPCM', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def cleanUp(self):
        self.debugPrint("Clean up and exit")
        # disconnect resources
        self.lcm.disconnect_transport()
        self.writeConfig()
        
    def debugPrint(self, msg):
        if self.debugArg or self.debug:
            print(msg)
    
    def checkArgs(self):
        self.debugPrint("Parse Args")
        parser = argparse.ArgumentParser(description='LLAP Config Me Client')
        parser.add_argument('-d', '--debug',
                            help='Extra Debug Output, overrides LLAPCM.cfg setting',
                            action='store_true')
        
        self.args = parser.parse_args()
        
        if self.args.debug:
            self.debugArg = True
        else:
            self.debugArg = False


    def readConfig(self):
        self.debugPrint("Reading Config")
        
        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self.configFileDefault))
        except:
            self.debugPrint("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self.configFile):
            self.debugPrint("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self.debugPrint("No Config Loaded, Quitting")
            sys.exit()
        
        self.debug = self.config.getboolean('Shared', 'debug')
        
        try:
            f = open(self.config.get('Shared', 'versionfile'))
            self.currentVersion = f.read()
            f.close()
        except:
            pass

    def writeConfig(self):
        self.debugPrint("Writing Config")
        with open(self.configFile, 'wb') as configfile:
            self.config.write(configfile)

    def loadDevices(self):
        self.debugPrint("Loading device List")
        try:
            with open(self.devFile, 'r') as f:
                read_data = f.read()
            f.closed
            
            self.devices = json.loads(read_data)['Devices']
    
        except IOError:
            self.debugPrint("Could Not Load DevList File")
            self.devices = [
                            {'id': 0,
                             'Description': 'Error loading DevList file'
                            }]




if __name__ == "__main__":
    app = LLAPCongfigMeClient()
    app.on_excute()