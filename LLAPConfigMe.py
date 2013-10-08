#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAP ConfigMe
    Copyright (c) 2013 Ciseco Ltd.
    
    Author: Matt Lloyd
    
    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    
"""

from Tkinter import *
import ttk
import sys
import os
import subprocess
import argparse
import math
import serial
import json
import urllib2
import httplib
import shutil
import ConfigParser
import tkMessageBox
import threading
import Queue
import zipfile
import time as time_
#import ImageTk
from Tabs import *


if sys.platform == 'darwin':
    port = '/dev/tty.usbmodem000001'
elif sys.platform == 'win32':
    port = ''
else:
    port = '/dev/ttyAMA0'

baud = 9600

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
        self.configFile = "LLACPCM.cfg"
        self.devFile = "DevList.json"
        self.myNodesFile = "MyNodes.json"
        
        self.widthMain = 750
        self.heightMain = 600
        self.heightTab = self.heightMain - 40
        self.proc = []
        self.disableLaunch = False
        self.updateAvailable = False
        
        self._running = False


    def on_excute(self):
        """
            entry point for running
        """
        self.checkArgs()
        self.readConfig()
        self.loadDevices()

        self._running = True

        self.runConfigMe()

        self.cleanUp()


    def runConfigMe(self):
        self.debugPrint("Running Main GUI")
        self.master = tk.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self.endLauncher)
        self.master.geometry(
                 "{}x{}+{}+{}".format(self.widthMain,
                                      self.heightMain,
                                      self.config.get('Launcher',
                                                      'window_width_offset'),
                                      self.config.get('Launcher',
                                                      'window_height_offset')
                                      )
                             )
                         
     self.master.title("LLAP Config Me v{}".format(self.currentVersion))
     self.master.resizable(0,0)
     
     self.tabFrame = tk.Frame(self.master, name='tabFrame')
     self.tabFrame.pack(pady=2)
     
     self.initTabBar()
     self.initMain()
     self.initAdvanced()
     
     self.tBarFrame.show()
     
     if self.updateAvailable:
         self.master.after(500, self.offerUpdate)
                         
    self.master.mainloop()

    def endLauncher(self):
        self.debugPrint("End Launcher")
        position = self.master.geometry().split("+")
        self.config.set('Launcher', 'window_width_offset', position[1])
        self.config.set('Launcher', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def cleanUp(self):
        self.debugPrint("Clean up and exit")
        # disconnect resources

        self.writeConfig()
        
    def debugPrint(self, msg):
        if self.debugArg or self.debug:
            print(msg)
    
    def checkArgs(self):
        self.debugPrint("Parse Args")
        parser = argparse.ArgumentParser(description='LLAP Config Me Client')
        parser.add_argument('-d', '--debug',
                            help='Extra Debug Output, overrides wik.cfg setting',
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
            f = open(self.config.get('Update', 'versionfile'))
            self.currentVersion = f.read()
            f.close()
        except:
            pass

    def writeConfig(self):
        self.debugPrint("Writing Config")
        with open(self.configFile, 'wb') as configfile:
            self.config.write(configfile)



if __name__ == "__main__":
    app = LLAPCongfigMeClient(root)
    app.on_excute()