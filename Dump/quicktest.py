#! /usr/bin/env python

import serial
from time import sleep
ser = serial.Serial()
ser.port = '/dev/ttyACM0'
ser.baudrate = 9600
ser.open()

sleep(1)


ser.write("a??CONFIGME-")
sleep(1)
ser.write("a??THERM001-")
sleep(1)
ser.write("a??APVER2.0-")
sleep(1)
ser.write("a??CHDEVID--")

sleep(2)
ser.close()