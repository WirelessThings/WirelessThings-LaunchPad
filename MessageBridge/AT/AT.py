#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" AT command mode Class
    Ciseco AT command mode helper class

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
from time import time, sleep, gmtime, strftime
import serial
import logging

class AT():

    _inATMode = False

    def __init__(self, serialHandle=None, logger=None, event=None, gpioPin=None):
        self._serial = serialHandle or serial.Serial()
        if logger == None:
            logging.basicConfig(level=logging.DEBUG)
            self.logger = logging.getLogger()
        else:
            self.logger = logger

        self.event = event

        self.gpioPin = gpioPin

        if self.gpioPin:
            try:
                global GPIO
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.gpioPin, GPIO.OUT)
                GPIO.output(self.gpioPin, GPIO.HIGH)
            except ImportError:
                self.logger.warn("AT: Error importing RPi.GPIO. '+++' will be used instead of GPIO")
                self.gpioPin = None
            except:
                self.logger.warn("AT: Error setting GPIO. '+++' will be used instead of GPIO")
                self.gpioPin = None

    def __del__(self):
        pass

    def setupSerial(self, port, baud):
        """ If we are not passed a serial port on init this helper will open on
        """
        self._serial.port = port
        self._serial.baudrate = baud
        self._serial.timeout = 1
        try:
            self._serial.open()
        except serial.SerialException:
            self.logger.exception("AT: Failed to open port {}".format(self._serial.port))
            return False
        else:
            self.logger.info("AT: Opened the serial port")
            self._sleep(0.1)
            return True

    def _sleep(self, time):
        """ Sleep Helper to use therading event or sleep
        """
        if self.event:
            self.event.wait(time)
        else:
            sleep(time)

    def endSerial(self):
        """ Helper to close serial port if setupSerial was used
        """
        self._serial.close()
        self.logger.debug("AT: Close Serial port")

    def enterATMode(self, retries=2):
        global GPIO
        """ Enter AT command mode
            To enter AT mode we wait 1 seconds send +++
            wait 1 second
            we should get back an "OK\r"
            or
            we set the gpio pin specified on .cfg file or by arg
        """

        self.logger.debug("AT: Enter Command Mode")
        if self.gpioPin:
            GPIO.output(self.gpioPin, GPIO.LOW)
            self.logger.debug("AT: Entered AT Mode via GPIO")
            self._inATMode = True
            return True

        for r in range(retries):
            self._serial.flushInput()

            self._sleep(1)

            self._serial.write("+++")

            self._sleep(0.1)

            self._serial.flushInput()

            if self.waitForOK(1.5):
                self._inATMode = True
                return True
            else:
                self.logger.debug("AT: Send 'AT'")
                self._serial.write("AT\r")
                if self.waitForOK(0.5):
                    self.logger.debug("AT: Entered AT Mode")
                    self._inATMode = True
                    return True
        #if reaches here, not in AT mode
        self._inATMode = False
        return False

    def leaveATMode(self):
        global GPIO
        """ Leave AT commnand Mode
            there are two ways to leave AT Mode
            send "ATDN"
            or wait the 5 second timeout
        """
        self.logger.debug("AT: Leave Command Mode")
        if self._inATMode:
            if self.gpioPin:
                GPIO.output(self.gpioPin, GPIO.HIGH)
            else:
                self.sendATWaitForOK("ATDN", 5)
        return True

    def sendAT(self, command):
        """ Send and AT command
        """
        self.logger.debug("AT: Send command: {}".format(command))
        if self._inATMode:
            self._serial.flushInput();
            self._serial.write("{}\r".format(command))
            return True
        else:
            return False

    def sendATWaitForOK(self, command, timeout=1.5, retries=3):
        """ Send an AT command and wait of "OK\r"
            used for command that do not return anything
        """
        if not self._inATMode:
            #if not in AT Mode, try to enter the AT Mode
            self.enterATMode()                        
            if not self._inATMode: # if still not in AT Mode, return False
                return False
        
        retry = 0
        response = False
        while not response and retry < retries:
            self.sendAT(command)
            response = self.waitForOK(timeout)
            retry += 1
        return response

    def waitForOK(self, timeout=1.5):
        """ wait/look for an "OK\r" from the radio
        """
        self.logger.debug("AT: Wait for OK")
        starttime = time()
        buffer = ""
        char = ""
        while (time() - starttime) < timeout and char != "\r":
            char = self._serial.read()
            #self.logger.debug("AT: RX:{}".format(char))
            buffer += char

        if "OK\r" in buffer:
            self.logger.debug("AT: Got OK")
            return True
        elif "ERR\r" in buffer:
            self.logger.debug("AT: Got ERR")
            return False
        else:
            self.logger.debug("AT: OK timed out")
            return False

    def sendATWaitForResponse(self, command, timeout=1.5, retries=3):
        """ Send an AT command and wait for response followed by an "OK\r"            
            Otherwise returns False
        """
        if not self._inATMode:
            #if not in AT Mode, try to enter the AT Mode
            self.enterATMode()                        
            if not self._inATMode: # if still not in AT Mode, return False
                return False
            
        retry = 0
        response = False
        while not response and retry < retries:
            self.sendAT(command)
            response = self.waitForResponse(timeout)
            retry += 1        
        return response
        
           
    def waitForResponse(self, timeout=1.5):
        """ wait/look for response from the radio
        """

        self.logger.debug("AT: Wait for Response")
        starttime = time()
        buffer = ""
        char = ""
        while (time() - starttime) < timeout:
            char = self._serial.read()
            if char == '\r':
                break
            # self.logger.debug("AT: RX:{}".format(char))
            buffer += char

        ### receive the first line, if there's no info (or ERR), return False
        if buffer == "":
            self.logger.debug("AT: OK timed out")
            return False
        elif buffer == "OK":
            return False
        elif buffer == "ERR":
            self.logger.debug("AT: Got ERR")
            return False

        #receive the second line (expecting 'OK\r') to make sure that the data received is valid
        if self.waitForOK():
            return buffer

        return False



if __name__ == "__main__":
    app = AT()
    app.setupSerial('/dev/tty.usbmodem000001', 9600)

    app.enterATMode()

    app.sendATWaitForOK("AT")

    app.endSerial()
