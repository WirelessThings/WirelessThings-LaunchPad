#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, shutil
#copy the old .cfg files to new names
'''
    RenameFiles
    ../LLAPConfigMeUI/LLAPCM.cfg
    ../LLAPLauncher/launcher.cfg
'''
#listRename = ["../LLAPConfigMeUI/LLAPCM.cfg","../LLAPLauncher/launcher.cfg"]
# load the list of files to rename
f = open("FilesToRename", "r")
#listRename = [line.rstrip() for line in f]
listRename = []
newItems = []
i = 1
for line in f:
    print "line {}".format(line)
    if i % 2:
        listRename.append(line.rstrip())
    else:
        newItems.append(line.rstrip())
    i += 1
f.close()
#newItems = ["../ConfigurationWizard/configWiz.cfg", "../LaunchPad/Launch.cfg"]

print "Renaming Config Files..."
#i = 0
#for item in listRename:
for i in range(len(listRename)):
    print "item {}".format(listRename[i])
    if (os.path.exists(listRename[i])):
        os.rename(listRename[i], newItems[i])
        print "newItems {}".format(newItems[i])
#    i += 1


'''
    RemoveFiles
    ../LLAPConfigMeUI/*.*
    ../LLAPLauncher/*.*
    ../LLAPServer/*.*
    ../RunMe.py
    ../LLAP*.*
    ../LCR*.*
    ../*.txt
    ../Readme.*
    ../Dump
'''
'''
listRemove = [  "../Dump",
                "../LLAPConfigMeUI",
                "../LLAPCSVLog",
                "../LLAPLauncher",
                "../LLAPServer",
                "../py2exe",
                "../LCRexample.json",
                "../LLAPCM_defaults.cfg",
                "../LLAPConfigMe.py",
                "../LLAPConfigMeCore.py",
                "../LLAPConfigMeServer.py",
                "../LLAPDevices.json",
                "../Readme.odt",
                "../Readme.pdf",
                "../ReadMe.txt",
                "../ReleaseNotes.txt",
                "../RunMe.py"
                ]
'''

# load the list of files to remove
f = open("FilesToRemove", "r")
listRemove = [line.rstrip() for line in f]
f.close()
# remove the old version files and directories
print "Removing Files..."
for item in listRemove:
    print "item {}".format(item)
    if (os.path.exists(item)):
        if (os.path.isdir(item)):
            shutil.rmtree(item) #remove the dir even if aren`t empty
        else:
            os.remove(item)

#os.remove("FilesToRemove")
#os.remove("FilesToRename")
#os.remove("clean.py")
