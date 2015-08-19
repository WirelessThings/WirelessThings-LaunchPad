#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, shutil
# load the list of files to rename
listRename = []
newItems = []
f = open("FilesToRename", "r")
i = 1
for line in f:
    if i % 2:
        listRename.append(line.rstrip())
    else:
        newItems.append(line.rstrip())
    i += 1
f.close()

for i in range(len(listRename)):
    if (os.path.exists(listRename[i])):
        os.rename(listRename[i], newItems[i])

# load the list of files to remove
f = open("FilesToRemove", "r")
listRemove = [line.rstrip() for line in f]
f.close()

# remove the old version files and directories
for item in listRemove:
    if (os.path.exists(item)):
        if (os.path.isdir(item)):
            shutil.rmtree(item) #remove the dir even if aren`t empty
        else:
            os.remove(item)
#should autoDestroy at end?
#os.remove("FilesToRemove")
#os.remove("FilesToRename")
#os.remove("clean.py")
