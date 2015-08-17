#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" WirelessThings encryption setup helper
    
    Usage
    $ python encryptionSetup.py
    or
    $ ./encryptionSetup.py
    
    By default this script uses the /dev/ttyAMA0 serial port at 9600 baud
    Optionally you can specify a different port and baudrate via arguments as below
    
    $ ./encryptinoSetup.py -p /dev/ttyACM0 -b 115200


    
    Author: Matt Lloyd
    Copyright 2015 Ciseco Ltd.
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
    http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
    
"""

import sys
import os
import argparse
import serial
import logging
import AT
import re
import random

class encryptionSetup():
    
    _port = '/dev/ttyAMA0'  # default serial port
    _baudrate= 9600            #default baudrate
    _serialTimeout = 1     # serial port time out setting
    
    _defaultPANID = '5AA5'
    _defaultEncryptionKey = '000102030405060708090A0B0C0D0E0F'
    
    _panID = 0
    _encryption = False
    _encryptionKey = 0
    
    def __init__(self, logger=None):
        """Instantiation

        Setup basics
        """
        if hasattr(sys,'frozen'): # only when running in py2exe this exists
            self._path = sys.prefix
        else: # otherwise this is a regular python script
            self._path = os.path.dirname(os.path.realpath(__file__))

        # setup initial Logging
        logging.getLogger().setLevel(logging.NOTSET)
        self.logger = logging.getLogger('Message Bridge')
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.INFO)    # this should be INFO by default
        self._formatter = logging.Formatter('%(asctime)s - %(message)s')
        self._ch.setFormatter(self._formatter)
        self.logger.addHandler(self._ch)

    def __del__(self):
        """Destructor

        Close any open threads, and transports
        """
        # TODO: shut down anything we missed
        pass

    def run(self):
        """
           This is the main entry point
        """
        self._checkArgs()           # pull in the command line options
        
        if (self.args.debug == True):
            self.logger.info("Setting output level to DEBUG")
            self._ch.setLevel(logging.DEBUG)
        
        # setup the serial port
        self._serial = serial.Serial()
        if (self.args.port):
            self._serial.port = self.args.port
        else:
            self._serial.port = self._port
        
        if (self.args.baudrate):
            self._serial.baudrate = self.args.baudrate
        else:
            self._serial.baudrate = self._baudrate

        self._serial.timeout = self._serialTimeout
        
        # setup the at class
        self._at = AT.AT(serialHandle=self._serial, logger=self.logger)


        self.logger.info("This app will attempt to read the current PANID and encryption setting from the radio on port {}.".format(self._serial.port))
        self.logger.info("If factory default setting are found we will generate a new PANID and encryption key to setup your radio network")

        self.logger.debug("Attempting to open the serial port")
        self._serial.open()
        self.logger.debug("Port open")
        
        if self._readCurrent():
            if self._defaultPANID == self._panID and self._encryption == False and self._encryptionKey == self._defaultEncryptionKey:
                self.logger.info("Default settings found")

                self._generateNewSetings()
                if self._applySettings():
                    if self._saveSettings():
                        self.logger.info ("New setting have been successfully applied")
                        self._printSettings()
                else:
                    self.logger.info("Failed to correctly apply setting, no changes have been saved to the device")
                    self.exit()
            else:
                self.logger.info("Non default settings found, no changes have been made")
                self._printSettings()
                if (self.args.force):
                    self.logger.info("Setting update forced via command line")
                    self._generateNewSetings()
                    if self._applySettings():
                        if self._saveSettings():
                            self.logger.info ("New setting have been successfully applied")
                            self._printSettings()
                    else:
                        self.logger.info("Failed to correctly apply setting, no changes have been saved to the device")
                        self.exit()
        else:
            self.logger.info("Failed to read the current setting from your radio")
            self.exit()
        self.exit()

    def _checkArgs(self):
        """Parse the command line options
        """
        parser = argparse.ArgumentParser(description='Encryption Setup helper', formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-d', '--debug',
                            help='Enable extra debug output to console',
                            action='store_true'
                            )
        parser.add_argument('-p', '--port',
                            help="Override the serial port of {}".format(self._port)
                            )
        parser.add_argument('-b', '--baudrate',
                            help="Override the baudrate of {}".format(self._baudrate)
                            )
        parser.add_argument('-f', '--force',
                            help='Force overwrite setings even when none defualt, Use with caution',
                            action='store_true'
                            )

        self.args = parser.parse_args()

    def _readCurrent(self):
        self.logger.info("Attempting to read the current settings")

        self._serial.flushInput()

        if self._at.enterATMode():
            self._panID = self._at.sendATWaitForResponse("ATID")
            if not self._panID:
                self.logger.critical("readCurrent: Invalid PANID")
                return False
                
            self._encryption = self._at.sendATWaitForResponse("ATEE")
            if not self._encryption:
                self.logger.critical("readCurrent: Invalid Encryption")
                return False
            self._encryption = bool(int(self._encryption)) #convert the received encryption to bool
            
            self._encryptionKey = self._at.sendATWaitForResponse("ATEK")
            if not self._encryptionKey:
                self.logger.critical("readCurrent: Invalid encryptionKey")
                return False
                
            self._at.leaveATMode()
            return True
            
        self.logger.debug("readCurrent: Failed to enter on AT Mode")
        return False
    
    def _generateNewSetings(self):
        self.logger.info("Generating new Settings")
    
        # PANID between 0000 - EFFF (0-61439)
        self._panID = "{0:0{1}X}".format(random.randrange(0,61439,1),4)
        while self._panID == self._defaultPANID:
            self._panID = "{0:0{1}X}".format(random.randrange(0,61439,1),4)

        self._encryptionKey = "{0:0{1}X}".format(random.randrange(0,4340282366920938463463374607431768211456,1),32)
        while self._encryptionKey == self._defaultEncryptionKey:
            self._encryptionKey = "{0:0{1}X}".format(random.randrange(0,4340282366920938463463374607431768211456,1),32)

    def _applySettings(self):
        self.logger.info("Applying setting to radio")
        self._serial.flushInput()

        if self._at.enterATMode():
            self.logger.debug("Setting PAINID")
            if self._at.sendATWaitForOK("ATID{}".format(self._panID)):
                panID = self._at.sendATWaitForResponse("ATID")
                if not panID:
                    self.logger.critical("applySettings: Invalid PANID")
                    return False
                elif panID != self._panID:
                    self.logger.debug("applySettings: PAINID set did not not match got back: {}".format(panID))
                    return False
            if self._at.sendATWaitForOK("ATEE1"):
                encryption = self._at.sendATWaitForResponse("ATEE")
                if not encryption:
                    self.logger.critical("applySettings: Invalid Encryption")
                    return False
                elif encryption == "0": #convert the received encryption to bool
                    self.logger.debug("applySettings: Failed to turn on encryption")
                    return False
                self._encryption = bool(int(encryption))

            if self._at.sendATWaitForOK("ATEK{}".format(self._encryptionKey)):
                encryptionKey = self._at.sendATWaitForResponse("ATEK")
                if not encryptionKey:
                    self.logger.critical("applySettings: Invalid encryptionKey")
                    self._cleanUp()
                    return False
                elif encryptionKey != self._encryptionKey:
                    self.logger.debug("applySettings: key did not match, got back: {}".format(encryptionKey))
                    return False
                
            self._at.leaveATMode()
            return True
            
        self.logger.debug("readCurrent: Failed to enter on AT Mode")
        return False

    def _saveSettings(self):
        self.logger.debug("Apply and save settings")
        self._serial.flushInput()
        if self._at.enterATMode():
            if self._at.sendATWaitForOK("ATAC"):
                if self._at.sendATWaitForOK("ATWR"):
                    self._at.leaveATMode()
                    self.logger.debug("Settings applied and saved")
                    return True
                else:
                    self.logger.debug("Applied setting but failed to save settings")
            else:
                self.logger.debug("Failed to apply settings, save not attempted")
        return False

    def _printSettings(self):
        self.logger.info("Your radio network settings are")
        self.logger.info("PANID: {}".format(self._panID))
        
        if self._encryption:
            encryption = "Enabled"
        else:
            encryption = "Disabled"
        self.logger.info("Encryption is: {}".format(encryption))
        
        self.logger.info("Encryption Key: {}".format(self._encryptionKey))

    def _cleanUp(self):
        pass

    def exit(self):
        try:
            self._serial.close()
        except:
            self.logger.debug("Error closing the serial port")
        self.logger.info("Exiting")
        sys.exit(1)
# run code
if __name__ == "__main__" :
    app = encryptionSetup()
    app.run()