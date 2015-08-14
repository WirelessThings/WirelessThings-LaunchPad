# ConfigurationWizard.py
WirelessThings Device Configuration Wizard

## Description
The Device Configuration Wizard presents a interface that allows the configuration of Language of Things devices.  
The steps of the wizard are quite simple but a knowledge of appropriate Language of Things settings for a device is still needed.  
The Device Configuration Wizard use JSON over UDP to talk to a WirelessThings Message Bridge running on the local network.


< Need more of an explanation here>


## Requirements
The Device Configuration Wizard can be run on any system with the following requirements
* Python 2.7
* Network access to a running WirelessThings Message Bridge

## Invoking
Starting the Device Configuration Wizard can be done though several means as detailed below
Using a command line or shell form with in the ConfigurationWizard directory

    $ python ConfigurationWizard.py

or

    $ ./ConfigurationWizard.py

The Device Configuration Wizard can also be started from the WirelessThings LaunchPad
Select **02. Device Configuration Wizard** from the List of app's and click the Launch button

Double click, your OS may have a run action associated with python script files and double clicking will launch the Device Configuration Wizard. Some systems will just open the script in a text editor, if so use one of the methods above.

## JSON Debug window
The Device Configuration Wizard has an optional JSON debug window that can be enabled or disabled from the configuration files or the --debug command line option.  
This window shows the incoming and outgoing JSON packets.  
Incoming packets are showen in BLUE.  
Outgoing packets are showen in RED.

## Command line options

* -h --help  
Display help message

* -d --debug  
Enable debug output to console, overrides ConfigurationWizard.cfg setting
Note the debug level is still taken form ConfigurationWizard.cfg, use in conjunction with --log to change level

* -l LOG --log LOG  
Override the console debug logging level, requires one of the following arguments to set the level you wish to see.
DEBUG, INFO, WARNING, ERROR, CRITICAL

## Configuration file
The Device Configuration Wizard keeps its configuration settings in two files.  
The first is a default file with all the base settings (ConfigurationWizard_defaults.cfg), the second is a users local copy ConfigurationWizard.cfg.  
If you wish to change any setting you can edit the user file ConfigurationWizard.cfg with a text editor of your choice.  
The file is split into the following sections. Complete details of the option in each section can be found in the default config file.  
* Debug  
Control the debug output of the server, either to the console window or to a log file, each log (console, file) can have different level set.
* ConfigurationWizard  
Location of the JSON fie that describes the Language of Things devices and there commands  
Window offsets
* UDP  
Set the UDP ports the Message Bridge send and receives on
* LCR  
Advance Configuration options to change how Language of Things Config Requests are handled
It is posible to disable processing of LCR's if you are running multiple Message Bridges on the same network
