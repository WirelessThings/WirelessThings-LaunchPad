Out Line:

Modular Python base confguration system for LLAP v2.0 devices
Based around the new CONFIGME system

First pass at modules

LLAPConfigMe.py:
    Main wrapper, including wizzard GUI.
    run with -d to see debug output and open serial debug window
    
LLAPCongieMeCore.py:
    Core module for the ConfigMe logic
    run with -d to see debug output from test code
    
LLAPDevices.json:
    JSON device list, for diffrent device types, templates for GUI's
    Also includes defineition on LLAP 2.0 commands