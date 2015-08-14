# MessageBridge.py
WirelessThings Message Bridge for Language of Things message between Serial and UDP networks

## Description
MessageBridge.py provides a Message Bridge for Language of Things message between Serial and UDP networks
On the serial side it talks strick Language of Things On the UDP network it encodes/decodes the Language of Things messages using a JSON packet.
< Need more of an explanation here>


## Requirements
The Message Bridge can be run on any system with the following requirements
* Python 2.7
* pySerial
* WirelessThings radio with firmware version of at least Serial V0.88 or USB V0.53

## Invoking
Starting the Message Bridge can be done though several means as detailed below
Using a command line or shell form with in the MessageBridge directory

    $ python MessageBridge.py

or

    $ ./MessageBridge.py

The Message Bridge can be started from the WirelessThings LaunchPad
Select **01. Message Bridge** from the List of app's and click the Start button

Double click, your OS may have a run action associated with python script files and double clicking will launch the Message Bridge. Some systems will just open the script in a text editor, if so use one of the methods above.

## Running in the console (foreground)
If MessageBridge.py is run from the command line without any options it will run in the foreground, if console debug output is enable you will see this in your terminal, if you close the terminal session then the Message Bridge will be stopped.
To stop the service running use Ctrl-C after a short while the service will exit

## Running as a Daemon or Service (background)
Currently this is not yet supported on Windows.  
It is posible to have the Message Bridge run as a background process. Control of background mode is done with the command line options start, stop, restart and status.  
To check is a Message Bridge is running on the local machine you can use the status option  

    $ ./MessageBridge.py status

This will return weather the service is running or not

Start, Stop and Restart can all be used to control the service like so

    $ ./MessageBridge.py start


It is also posible to control the Message Bridge using the WirelessThings LaunchPad which has buttons for Start, Stop and Restart

## Install as Daemon or Service for start on boot
Currently this is not yet supported on Windows or OSX.  
It is posible to have the Message Bridge start automatically on boot.  
For Linux we provide a init.d script that can be found in the ./init.d/ folder. From the MessageBridge folder you can use the following commands to install the script.

    $ sudo cp ./init.d/messagebridge /etc/init.d/
    $ sudo chmod +x /etc/init.d/messagebridge
    $ sudo update-rc.d messagebridge defaults

At next reboot the Message Bridge will now start automatically

It is also posible to use the WirelessThings LaunchPad to install and remove this script using the Enable/Disable AutoStart button.

## Command line options
* -h --help  
Display help message

* -d --debug  
Enable debug output to console, overrides MessageBridge.cfg setting
Note the debug level is still taken form MessageBridge.cfg, use in conjunction with --log to change level

* -l LOG --log LOG  
Override the console debug logging level, requires one of the following arguments to set the level you wish to see.
DEBUG, INFO, WARNING, ERROR, CRITICAL

* {start, stop, restart, status}  
    To run and control a Message Bridge in the background use one of the following:  
    start = Starts as a background daemon/service  
    stop = Stops a daemon/service if running  
    restart = Restarts the daemon/service  
    status = Check if a Message Bridge is running  
    If none of the above are given and no daemon/service  
    is running then run in the current terminal

## Configuration file
Message Bridge keeps its configuration settings in a file called MessageBridge.cfg. This can be edited with a text editor of your choice.  
The file is split into the following sections. Complete details of the option in each section can be found in the config file.  
* Debug  
Control the debug output of the server, either to the console window or to a log file, each log (console, file) can have different level set.
* Serial  
Set the Serial port and baud rate for your radio
Set the name for this serial network as use in JSON packets
* UDP  
Set the UDP ports the Message Bridge send and receives on
* LCR  
Advance Configuration options to change how Language of Things messages are handled
It is posible to disable processing of LCR's if you are running multiple Message Bridges on the same network
