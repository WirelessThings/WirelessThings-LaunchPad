#LLAPServer.py
Transfer Service for LLAP message between Serial and UDP networks

##Description
LLAPServer.py provides a Transfer Service for LLAP message between Serial and UDP networks
On the serial side it talks strick LLAP. On the UDP network it encodes/decodes the LLAP messages using a JSON packet.
< Need more of an explanation here>


## Requirements
The transfer service can be run on any system with the following requirements
* Python 2.7
* pySerial
* Ciseco radio with firmware version of at least Serial V0.88 or USB V0.53

##Invoking
Starting the transfer service can be done though several means as detailed below
Using a command line or shell form with in the LLAPServer directory

    $ python LLAPServer.py

or

    $ ./LLAPServer.py

The transfer service can be started from the LLAP Launcher GUI
Select **01. Transfer Service** from the List of app's and click the Start button

Double click, your OS may have a run action associated with python script files and double clicking will launch the Transfer Service. Some systems will just open the script in a text editor, if so use one of the methods above.

##Running in the console (foreground)
If LLAPServer.py is run from the command line without any options it will run in the foreground, if console debug output is enable you will see this in your terminal, if you close the terminal session then the Transfer Service will be stopped.
To stop the service running use Ctrl-C after a short while the service will exit

##Running as a Daemon or Service (background)
Currently this is not yet supported on Windows.  
It is posible to have the transfer service run as a background process. Control of background mode is done with the command line options start, stop, restart and status.  
To check is a Transfer Service is running on the local machine you can use the status option  

    $ ./LLAPServer.py status

This will return weather the service is running or not

Start, Stop and Restart can all be used to control the service like so

    $ ./LLAPServer.py start


It is also posible to control the transfer service using the LLAP Launcher UI which has buttons for Start, Stop and Restart

##Install as Daemon or Service for start on boot
Currently this is not yet supported on Windows or OSX.  
It is posible to have the transfer service start automatically on boot.  
For Linux we provide a init.d script that can be found in the ./init.d/ folder. From the LLAPServer folder you can use the following commands to install the script.

    $ sudo cp ./init.d/llapserver /etc/init.d/
    $ sudo chmod +x /etc/init.d/llapserver
    $ sudo update-rc.d llapserver defaults

At next reboot the LLAPService will now start automatically

It is also posible to use the LLAP Launcher UI to install and remove this script using the Enablde/Disable AutoStart button.

##Command line options

* -h --help  
Display help message

* -d --debug  
Enable debug output to console, overrides LLAPServer.cfg setting
Note the debug level is still taken form LLAPServer.cfg, use in conjunction with --log to change level

* -l LOG --log LOG  
Override the console debug logging level, requires one of the following arguments to set the level you wish to see.
DEBUG, INFO, WARNING, ERROR, CRITICAL

* {start, stop, restart, status}  
    To run and control a LLAPServer in the background use one of the following:  
    start = Starts as a background daemon/service  
    stop = Stops a daemon/service if running  
    restart = Restarts the daemon/service  
    status = Check if a LLAP transfer serveice is running  
    If none of the above are given and no daemon/service  
    is running then run in the current terminal

##Configuration file
LLAPServer keeps its configuration settings in a file called LLAPServer.cfg. This can be edited with a text editor of your choice.  
The file is split into the following sections. Complete details of the option in each section can be found in the config file.  
* Debug  
Control the debug output of the server, either to the console window or to a log file, each log (console, file) can have different level set.
* Serial  
Set the Serial port and baud rate for your radio
Set the name for this serial network as use in JSON packets
* UDP  
Set the UDP ports the Transfer service send and receives on
* LCR  
Advance Configuration options to change how LLAP Config Requests are handled
It is posible to disable processing of LCR's if you are running multiple LLAP Transfer Services on the same network
