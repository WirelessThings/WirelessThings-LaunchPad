#LLAPConfigMe.py
Configuration UI for LLAP+ devices

##Description
The LLAP Configuration UI presents a wizard style intreface that allows the configuration of LLAP+ devices.  
The steps of the wizard are quite simple but a knowledge of appropriate LLAP settings for a device is still needed.  
The Configuration UI use JSON over UDP to talk to a LLAP Transfer service running on the local network.


< Need more of an explanation here>


## Requirements
The Configuration UI can be run on any system with the following requirements
* Python 2.7
* Network access to a running LLAP Transfer Service

##Invoking
Starting the configuration UI can be done though several means as detailed below
Using a command line or shell form with in the LLAPConfigMeUI directory

    $ python LLAPConfigMe.py

or

    $ ./LLAPConfigMe.py

The Configuration UI can also be started from the LLAP Launcher GUI
Select **02. Configuration UI** from the List of app's and click the Launch button

Double click, your OS may have a run action associated with python script files and double clicking will launch the Configuration UI. Some systems will just open the script in a text editor, if so use one of the methods above.

## JSON Debug window
The Configuration UI has an optional JSON debug window that can be enabled or disabled from the configuration files or the --debug command line option.  
This window shows the incoming and outgoing JSON packets.  
Incoming packets are showen in BLUE.  
Outgoing packets are showen in RED.

##Command line options

* -h --help  
Display help message

* -d --debug  
Enable debug output to console, overrides LLAPCFM.cfg setting
Note the debug level is still taken form LLAPCFM.cfg, use in conjunction with --log to change level

* -l LOG --log LOG  
Override the console debug logging level, requires one of the following arguments to set the level you wish to see.
DEBUG, INFO, WARNING, ERROR, CRITICAL

##Configuration file
LLAPConfigMe keeps its configuration settings in two files.  
The first is a default file with all the base settings (LLAPCM_defaults.cfg), the second is a users local copy LLAPCM.cfg.  
If you wish to change any setting you can edit the user file LLAPCM.cfg with a text editor of your choice.  
The file is split into the following sections. Complete details of the option in each section can be found in the default config file.  
* Debug  
Control the debug output of the server, either to the console window or to a log file, each log (console, file) can have different level set.
* LLAPCM  
Location of the JSON fie that describes the LLAP+ devices and there commands  
Window offsets
* UDP  
Set the UDP ports the Transfer service send and receives on
* LCR  
Advance Configuration options to change how LLAP Config Requests are handled
It is posible to disable processing of LCR's if you are running multiple LLAP Transfer Services on the same network
