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
import argparse
import serial
import json
import ConfigParser
import tkMessageBox
import threading
import Queue
import time as time_
#import ImageTk
from Tabs import *


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
        self.devFile = "LLAPConfigMeDevices.json"
        self.myNodesFile = "MyNodes.json"
        
        self.widthMain = 750
        self.heightMain = 600
        self.heightTab = self.heightMain - 40

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
                                      self.config.get('LLAPCM',
                                                      'window_width_offset'),
                                      self.config.get('LLAPCM',
                                                      'window_height_offset')
                                      )
                             )

        self.master.title("LLAP Config Me v{}".format(self.currentVersion))
        self.master.resizable(0,0)

        self.tabFrame = tk.Frame(self.master, name='tabFrame')
        self.tabFrame.pack(pady=2)

        self.initTabBar()
        self.initMain()

        self.tBarFrame.show()
                         
        self.master.mainloop()

    def initTabBar(self):
        self.debugPrint("Setting up TabBar")
        # tab button frame
        self.tBarFrame = TabBar(self.tabFrame, "Main", fname='tabBar')
        self.tBarFrame.config(relief=tk.RAISED, pady=4)
        
        # tab buttons
        tk.Button(self.tBarFrame, text='Quit', command=self.endLauncher
                  ).pack(side=tk.RIGHT)
    
    def initMain(self):
        self.debugPrint("Setting up Main Tab")
        iframe = Tab(self.tabFrame, "Main", fname='main')
        iframe.config(relief=tk.RAISED, borderwidth=2, width=self.widthMain,
                      height=self.heightTab)
        self.tBarFrame.add(iframe)
    
                  
        #canvas = tk.Canvas(iframe, bd=0, width=self.widthMain-4,
        #                       height=self.heightTab-4, highlightthickness=0)
        #canvas.grid(row=0, column=0, columnspan=3, rowspan=5)

        tk.Canvas(iframe, bd=0, highlightthickness=0, width=self.widthMain-4,
                  height=28).grid(row=1, column=1, columnspan=3)
        tk.Canvas(iframe, bd=0, highlightthickness=0, width=150,
                  height=self.heightTab-4).grid(row=1, column=1, rowspan=3)
                  
        tk.Label(iframe, text="Select an App to Launch").grid(row=1, column=1,
                                                            sticky=tk.W)

        lbframe = tk.Frame(iframe, bd=2, relief=tk.SUNKEN)


    def endLauncher(self):
        self.debugPrint("End Launcher")
        position = self.master.geometry().split("+")
        self.config.set('LLAPCM', 'window_width_offset', position[1])
        self.config.set('LLAPCM', 'window_height_offset', position[2])
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
            
            self.appList = json.loads(read_data)['Devices']
        except IOError:
            self.debugPrint("Could Not Load AppList File")
            self.appList = [
                            {'id': 0,
                             'Description': 'Error loading DevList file'
                            }]




if __name__ == "__main__":
    app = LLAPCongfigMeClient()
    app.on_excute()