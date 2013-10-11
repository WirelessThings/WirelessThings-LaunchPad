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
ser.write("a??CONFIGME-")
sleep(1)
ser.write("a??AWAKE005M")
sleep(1)
ser.write("a??THERM001-")
sleep(1)
ser.write("a??PANID5AA5")
sleep(1)
ser.write("a??RETRIES5-")
sleep(1)
ser.write("a??INTVL000S")
sleep(1)
ser.write("a??WAKEC10--")
sleep(1)
ser.write("a??BVAL3977-")
sleep(1)
ser.write("a??RNOM10---")
sleep(1)
ser.write("a??IR22-----")
sleep(1)
ser.write("a??SRES10---")





sleep(2)
ser.close()