Out Line:

Modular Python base confguration system for LLAP v2.0 devices
Based around the new CONFIGME system

First pass at modules

LLAPConfigMe.py:
    Main wrapper, including wizzard GUI.
    
LLAPCongieMeCore.py:
    Core module for the ConfigMe logic
    
    
    
LLAPConfigMeDevices.json:
    JSON device list, for diffrent device types, templates for GUI's
    
LLAPSerial.py:
    Serial Transfrer layer
    
MyNodes.json:
    JSON device node list
    
    
Note part of the systems

wiz.py:
    sample pyton TK wizard code


Dev Notes:

quick update to LLAPSerial to make interface a handel building and decode of llap messages


layers
GUI
ConfigMe
    Transaction layer
    Transport Layer


GUI passed config request on ConfigMe


First empty serial buffer and wait for next a??CONFIGME- (with time out)

hmm might be easier with direct serial buffer acees as can clear down first and wait for next configme
only have 10ms to reply so need to be quick
we expect a configme every 5 sec, so clearing buffer and replying on arival should only block for 5sec

bah

ok core v2

short life? just open and close serial long enuff todo a configRequest?
still needs to inti with life of app, 
app should call function with its condig request, as we need to return it

still needs a thread seprate from the gui
should GUI take care of threading? no we just want to thread the transaction, which can block untill 12chars arrive as needed



init 
    setupThread
    setupQueue

setPort
    determin trnsport based on port type
    setup serial connection basics

processRequest(configRequest)
    try open port
    try connect
    start thread, passing in config request
    
    wait for item in queue and thread to stop
    close port
    return queue item (configRequest with replies

        


questThread?
    we hace a config request and open serial port
    check devtype first
    start 45sec timeout
    so empty buffer
    wait for 12
        look for ?? configme
        send devtype
        wait for 12 reply
        if matches carry on
        else fail, 
            return devtype in replies only
        
        for each request:
            send request
            wait for 12
                if confgirme 
                    missed window resend
                    
                got reply?
                    filleit
                not for us, next 12?
                    
        got replies 
        return via queue
        stop     
            