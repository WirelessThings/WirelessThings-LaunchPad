#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" AT command mode Class
    Ciseco AT command mode helper class
    Copyright (c) 2014 Ciseco Ltd.

    Author: Matt Lloyd

    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

"""
import sys
from time import time, sleep, gmtime, strftime
import serial
import logging

class AT():

    _inATMode = False

    def __init__(self, serialHandle=None, logger=None, event=None):
        self._serial = serialHandle or serial.Serial()
        if logger == None:
            logging.basicConfig(level=logging.DEBUG)
            self.logger = logging.getLogger()
        else:
            self.logger = logger

        self.event = event

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
            return Fasle
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
        """ Enter AT command mode
            To enter AT mode we wait 1 seconds send +++
            wait 1 second
            we should get back an "OK\r"
        """
        self.logger.debug("AT: Enter Command Mode")
        for r in range(retries):
            self._serial.flushInput()

            self._sleep(1)

            self._serial.write("+++")

            self._sleep(0.1)

            self._serial.flushInput()

            if self.waitForOK(1.5):
                self._inATMode = True
                return True
        return False

    def leaveATMode(self):
        """ Leave AT commnand Mode
            there are two ways to leave AT Mode
            send "ATDN"
            or wait the 5 second timeout
        """
        self.logger.debug("AT: Leave Command Mode")
        if self._inATMode:
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

    def sendATWaitForOK(self, command, timeout=1.5):
        """ Send an AT command and wait of "OK\r"
            used for command that do not return anything
        """
        if self._inATMode:
            self.sendAT(command)
            return self.waitForOK(timeout)
        else:
            return False

    def waitForOK(self, timeout=1.5):
        """ wait/look for an "OK\r" from the radio
        """
        self.logger.debug("AT: Wait for OK")
        starttime = time()
        buffer = ""
        char = ""
        while (time() - starttime) < timeout and char != "\r":
            char = self._serial.read()
            # self.logger.debug("AT: RX:{}".format(char))
            buffer += char

        if buffer == "OK\r":
            self.logger.debug("AT: Got OK")
            return True
        elif buffer == "ERR\r":
            self.logger.debug("AT: Got ERR")
            return False
        else:
            self.logger.debug("AT: OK timed out")
            return False

if __name__ == "__main__":
    app = AT()
    app.setupSerial('/dev/tty.usbmodem000001', 9600)

    app.enterATMode()

    app.sendATWaitForOK("AT")

    app.endSerial()
