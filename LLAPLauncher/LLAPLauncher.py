#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LLAP Launcher
    Copyright (c) 2014 Ciseco Ltd.
    
    Author: Matt Lloyd
    
    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    
"""
import Tkinter as tk
import ttk
import sys
import os
import subprocess
import argparse
import json
import urllib2
import httplib
import shutil
import ConfigParser
import tkMessageBox
import threading
import Queue
import zipfile
import time as time_
import tkFileDialog
from distutils import dir_util
import stat
from Tabs import *

"""
   todo list:-
   
   Move advance list from json into py
   
   switch to debug prints to logging
   
   apps list to be llap service
   
   auto update to new folder
   
   start(restart?)
   stop
   auto start buttons
   
   service status indicators
   
   dont kill other on exit
   
   check if service is already runnning
   
   service should record a pid file?
   
   restart services on update
   
   
"""

class LLAPLauncher:
    _name = "LLAP Launcher"
    _autoStartText = {
                      'enable': "Enable Autostart",
                      'disable': "Disable Autostart"
                     }
    
    password = None
    def __init__(self):
        self.debug = False # until we read config
        self.debugArg = False # or get command line
        self.configFileDefault = "launcher_defaults.cfg"
        self.configFile = "launcher.cfg"
        self.appFile = "AppList.json"

        self.widthMain = 550
        self.heightMain = 300
        self.heightTab = self.heightMain - 40
        self.proc = []
        self.disableLaunch = False
        self.updateAvailable = False

        self._running = False
    
    def on_excute(self):
        self.checkArgs()
        self.readConfig()
        self.loadApps()
        
        if self.args.noupdate:
            self.checkForUpdate()

        self._running = True

        self.runLauncher()

        self.cleanUp()
        
    def restart(self):
        # restart after update
        args = sys.argv[:]
        
        self.debugPrint('Re-spawning %s' % ' '.join(args))
        args.append('-u')   # no need to check for update again
        args.insert(0, sys.executable)
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        
        os.execv(sys.executable, args)

    def endLauncher(self):
        self.debugPrint("End Launcher")
        position = self.master.geometry().split("+")
        self.config.set('Launcher', 'window_width_offset', position[1])
        self.config.set('Launcher', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def cleanUp(self):
        self.debugPrint("Clean up and exit")
        # disconnect resources
        # kill child's??
        for c in self.proc:
            if c.poll() == None:
                c.terminate()
        self.writeConfig()
    
    def debugPrint(self, msg):
        if self.debugArg or self.debug:
            print(msg)

    def checkArgs(self):
        self.debugPrint("Parse Args")
        parser = argparse.ArgumentParser(description=self._name)
        parser.add_argument('-u', '--noupdate',
                            help='disable checking for update',
                            action='store_false')
        parser.add_argument('-d', '--debug',
                            help='Extra Debug Output, overrides launcher.cfg setting',
                            action='store_true')
        
        self.args = parser.parse_args()
        
        if self.args.debug:
            self.debugArg = True
        else:
            self.debugArg = False

    def checkForUpdate(self):
        self.debugPrint("Checking for update")
        # go download version file
        try:
            request = urllib2.urlopen(self.config.get('Update', 'updateurl') +
                                      self.config.get('Update', 'versionfile'))
            self.newVersion = request.read()

        except urllib2.HTTPError, e:
            self.debugPrint('Unable to get latest version info - HTTPError = ' +
                            str(e.code))
            self.newVersion = False

        except urllib2.URLError, e:
            self.debugPrint('Unable to get latest version info - URLError = ' +
                            str(e.reason))
            self.newVersion = False
        
        except httplib.HTTPException, e:
            self.debugPrint('Unable to get latest version info - HTTPException')
            self.newVersion = False

        except Exception, e:
            import traceback
            self.debugPrint('Unable to get latest version info - Exception = ' +
                            traceback.format_exc())
            self.newVersion = False

        if self.newVersion:
            self.debugPrint(
                "Latest Version: {}, Current Version: {}".format(
                              self.newVersion, self.currentVersion)
                            )
            if float(self.currentVersion) < float(self.newVersion):
                self.debugPrint("New Version Available")
                self.updateAvailable = True
        else:
            self.debugPrint("Could not check for new Version")
            
    def offerUpdate(self):
        self.debugPrint("Ask to update")
        if tkMessageBox.askyesno("{} Update Available".format(self._name),
                                 ("There is an update for {} available would "
                                  "you like to download it?".format(self._name))
                                 ):
            self.updateFailed = False
            # grab zip size for progress bar length
            try:
                u = urllib2.urlopen(self.config.get('Update', 'updateurl') +
                                    self.config.get('Update',
                                                    'updatefile'
                                                    ).format(self.newVersion))
                meta = u.info()
                self.file_size = int(meta.getheaders("Content-Length")[0])
            except urllib2.HTTPError, e:
                self.debugPrint('Unable to get download file size - HTTPError = ' +
                                str(e.code))
                self.updateFailed = "Unable to get download file size"
            
            except urllib2.URLError, e:
                self.debugPrint('Unable to get download file size- URLError = ' +
                                str(e.reason))
                self.updateFailed = "Unable to get download file size"
            
            except httplib.HTTPException, e:
                self.debugPrint('Unable to get download file size- HTTPException')
                self.updateFailed = "Unable to get download file size"
            
            except Exception, e:
                import traceback
                self.debugPrint('Unable to get download file size - Exception = ' +
                                traceback.format_exc())
                self.updateFailed = "Unable to get download file size"
            
            if self.updateFailed:
                tkMessageBox.showerror("Update Failed", self.updateFailed)
            else:
                position = self.master.geometry().split("+")
                
                self.progressWindow = tk.Toplevel()
                self.progressWindow.geometry("+{}+{}".format(
                                                int(position[1]
                                                    )+self.widthMain/4,
                                                int(position[2]
                                                    )+self.heightMain/4
                                                             )
                                             )
                self.progressWindow.title("Downloading Zip Files")
                
                tk.Label(self.progressWindow, text="Downloading Zip Progress"
                         ).pack()
                
                self.progressBar = tk.IntVar()
                ttk.Progressbar(self.progressWindow, orient="horizontal",
                                length=200, mode="determinate",
                                maximum=self.file_size,
                                variable=self.progressBar).pack()
                
                self.downloadThread = threading.Thread(target=self.downloadUpdate)
                self.progressQueue = Queue.Queue()
                self.downloadThread.start()
                self.progressUpdate()

    def progressUpdate(self):
        self.debugPrint("Download Progress Update")
        value = self.progressQueue.get()
        self.progressBar.set(value)
        self.progressQueue.task_done()
        if self.updateFailed:
            self.progressWindow.destroy()
            tkMessageBox.showerror("Update Failed", self.updateFailed)
        elif value < self.file_size:
            self.master.after(1, self.progressUpdate)
        else:
            self.progressWindow.destroy()
            self.doUpdate(self.config.get('Update', 'downloaddir') +
                          self.config.get('Update',
                                          'updatefile').format(self.newVersion))

    def downloadUpdate(self):
        self.debugPrint("Downloading Update Zip")
        
        url = (self.config.get('Update', 'updateurl') +
               self.config.get('Update', 'updatefile').format(self.newVersion))
               
        self.debugPrint(url)
        # mk dir Download
        if not os.path.exists(self.config.get('Update', 'downloaddir')):
            os.makedirs(self.config.get('Update', 'downloaddir'))
        
        localFile = (self.config.get('Update', 'downloaddir') +
                     self.config.get('Update', 'updatefile'
                                     ).format(self.newVersion))
        
        self.debugPrint(localFile)

        try:
            u = urllib2.urlopen(url)
            f = open(localFile, 'wb')
            meta = u.info()
            file_size = int(meta.getheaders("Content-Length")[0])
            self.debugPrint("Downloading: {0} Bytes: {1}".format(url,
                                                                 file_size))

            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
                
                file_size_dl += len(buffer)
                f.write(buffer)
                p = float(file_size_dl) / file_size
                status = r"{0}  [{1:.2%}]".format(file_size_dl, p)
                status = status + chr(8)*(len(status)+1)
                self.debugPrint(status)
                self.progressQueue.put(file_size_dl)

            f.close()
        except urllib2.HTTPError, e:
            self.debugPrint('Unable to get download file - HTTPError = ' +
                            str(e.code))
            self.updateFailed = "Unable to get download file"
        
        except urllib2.URLError, e:
            self.debugPrint('Unable to get download file - URLError = ' +
                            str(e.reason))
            self.updateFailed = "Unable to get download file"
        
        except httplib.HTTPException, e:
            self.debugPrint('Unable to get download file - HTTPException')
            self.updateFailed = "Unable to get download file"
        
        except Exception, e:
            import traceback
            self.debugPrint('Unable to get download file - Exception = ' +
                            traceback.format_exc())
            self.updateFailed = "Unable to get download file"

    def manualZipUpdate(self):
        self.debugPrint("Location Zip for Update")
        self.updateFailed = False
        
        filename = tkFileDialog.askopenfilename(title="Please select the {} Update zip".format(self._name),
                                                filetypes = [("Zip Files",
                                                              "*.zip")])
        self.debugPrint("Given file name of {}".format(filename))
        # need to check we have a valid zip file name else updateFailed
        if filename == '':
            # cancelled so do nothing
            self.updateFailed = True
            self.debugPrint("Update cancelled")
        elif filename.endswith('.zip'):
            # do the update
            self.doUpdate(filename)

            
    def doUpdate(self, file):
        self.debugPrint("Doing Update with file: {}".format(file))
    
        self.zfobj = zipfile.ZipFile(file)
        self.extractDir = "../"
        # self.config.get('Update', 'downloaddir') + self.newVersion + "/"
        # if not os.path.exists(self.extractDir):
        #       os.mkdir(self.extractDir)
        
        self.zipFileCount = len(self.zfobj.namelist())

        position = self.master.geometry().split("+")
        
        self.progressWindow = tk.Toplevel()
        self.progressWindow.geometry("+{}+{}".format(
                                             int(position[1])+self.widthMain/4,
                                             int(position[2])+self.heightMain/4
                                                     )
                                     )
            
        self.progressWindow.title("Extracting Zip Files")

        tk.Label(self.progressWindow, text="Extracting Zip Progress").pack()

        self.progressBar = tk.IntVar()
        ttk.Progressbar(self.progressWindow, orient="horizontal",
                     length=200, mode="determinate",
                     maximum=self.zipFileCount,
                     variable=self.progressBar).pack()
                     
        self.zipThread = threading.Thread(target=self.zipExtract)
        self.progressQueue = Queue.Queue()
        self.zipThread.start()
        self.zipProgressUpdate()

    def zipProgressUpdate(self):
        self.debugPrint("Zip Progress Update")
        
        value = self.progressQueue.get()
        self.progressBar.set(value)
        self.progressQueue.task_done()
        if self.updateFailed:
            self.progressWindow.destroy()
            tkMessageBox.showerror("Update Failed", self.updateFailed)
        elif value < self.zipFileCount:
            self.master.after(1, self.zipProgressUpdate)
        else:
            self.progressWindow.destroy()
            self.restart()

    def zipExtract(self):
        count = 0
        for name in self.zfobj.namelist():
            count += 1
            self.progressQueue.put(count)
            (dirname, filename) = os.path.split(name)
            if dirname.startswith("__MACOSX") or filename == ".DS_Store":
                pass
            else:
                self.debugPrint("Decompressing " + filename + " on " + dirname)
                self.zfobj.extract(name, self.extractDir)
                if name.endswith(".py"):
                    self.debugPrint("Setting execute bits")
                    st = os.stat(self.extractDir + name)
                    os.chmod(self.extractDir + name, (st.st_mode | stat.S_IXUSR | stat.S_IXGRP))
                time_.sleep(0.1)


    def runLauncher(self):
        self.debugPrint("Running Main Launcher")
        self.master = tk.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self.endLauncher)
        self.master.geometry(
             "{}x{}+{}+{}".format(self.widthMain,
                                  self.heightMain,
                                  self.config.get('Launcher',
                                                  'window_width_offset'),
                                  self.config.get('Launcher',
                                                  'window_height_offset')
                                  )
                             )
                             
        self.master.title("LLAP Launcher v{}".format(self.currentVersion))
        self.master.resizable(0,0)
        
        self.tabFrame = tk.Frame(self.master, name='tabFrame')
        self.tabFrame.pack(pady=2)
        
        self.initTabBar()
        self.initMain()
        self.initAdvanced()
        
        self.tBarFrame.show()
        
        if self.updateAvailable:
            self.master.after(500, self.offerUpdate)
        
        self.master.mainloop()

    def initTabBar(self):
        self.debugPrint("Setting up TabBar")
        # tab button frame
        self.tBarFrame = TabBar(self.tabFrame, "Main", fname='tabBar')
        self.tBarFrame.config(relief=tk.RAISED, pady=4)
        
        # tab buttons
        tk.Button(self.tBarFrame, text='Quit', command=self.endLauncher
               ).pack(side=tk.RIGHT)
        #tk.Label(self.tBarFrame, text=self.currentVersion).pack(side=tk.RIGHT)

    def initMain(self):
        self.debugPrint("Setting up Main Tab")
        iframe = Tab(self.tabFrame, "Main", fname='launcher')
        iframe.config(relief=tk.RAISED, borderwidth=2, width=self.widthMain,
                      height=self.heightTab)
        self.tBarFrame.add(iframe)
        
        
        #canvas = tk.Canvas(iframe, bd=0, width=self.widthMain-4,
        #                       height=self.heightTab-4, highlightthickness=0)
        #canvas.grid(row=0, column=0, columnspan=3, rowspan=5)

        tk.Canvas(iframe, bd=0, highlightthickness=0, width=self.widthMain-4,
                  height=28).grid(row=1, column=1, columnspan=3)
        tk.Canvas(iframe, bd=0, highlightthickness=0, width=150,
                  height=self.heightTab-4).grid(row=1, column=1, rowspan=3)
        
        tk.Label(iframe, text="Select an App to Launch").grid(row=1, column=1,
                                                              sticky=tk.W)
        
        lbframe = tk.Frame(iframe, bd=2, relief=tk.SUNKEN)

        self.scrollbar = tk.Scrollbar(lbframe)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.appSelect = tk.Listbox(lbframe, bd=0, height=10,
                                    yscrollcommand=self.scrollbar.set)
        self.appSelect.bind('<<ListboxSelect>>', self.onAppSelect)
        self.appSelect.pack()

        self.scrollbar.config(command=self.appSelect.yview)

        lbframe.grid(row=2, column=1, sticky=tk.W+tk.E+tk.N+tk.S, padx=2)

        for n in range(len(self.appList)):
            self.appSelect.insert(n, "{}: {}".format(n+1,
                                                     self.appList[n]['Name']))

        self.buttonFrame = tk.Frame(iframe)
        self.buttonFrame.grid(row=3, column=1, columnspan=3, sticky=tk.W+tk.E)
        
        self.initLaunchFrame()
        self.initSSRFrame()

        self.appText = tk.Label(iframe, text="", width=40, height=11,
                                relief=tk.RAISED, justify=tk.LEFT, anchor=tk.NW)
        self.appText.grid(row=2, column=3, rowspan=2, sticky=tk.W+tk.E+tk.N,
                          padx=2)

        self.appSelect.selection_set(0)
        self.onAppSelect(None)
        
        #self.appText.insert(tk.END, )
        #self.appText.config(state=tk.DISABLED)
        #tk.Text(iframe).grid(row=0, column=1, rowspan=2)


    def initSSRFrame(self):
        # setup start|stop|restart buttons
        self.SSRFrame = tk.Frame(self.buttonFrame, name='ssrFrame')

        tk.Button(self.SSRFrame, name='start', text="Start",
                  command=lambda: self.launch('start'), state=tk.DISABLED
                  ).pack(side=tk.LEFT)
        tk.Button(self.SSRFrame, name='stop', text="Stop",
                  command=lambda: self.launch('stop'), state=tk.DISABLED
                  ).pack(side=tk.LEFT)
        tk.Button(self.SSRFrame, name='restart', text="Restart",
                  command=lambda: self.launch('start'), state=tk.DISABLED
                  ).pack(side=tk.LEFT)

        self.serviceButton = tk.Button(self.SSRFrame, name='autostart',
                                       text=self._autoStartText['enable'],
                                       command=self.autostart,
                                       state=tk.DISABLED)

    def initLaunchFrame(self):
        # launch button
        self.launchFrame = tk.Frame(self.buttonFrame, name='launchFrame')
        tk.Button(self.launchFrame, name='launch', text="Launch",
                  command=lambda: self.launch('launch')
                  ).pack(side=tk.LEFT)

        if self.disableLaunch:
            self.launchFrame.children['launch'].config(state=tk.DISABLED)

    def initAdvanced(self):
        self.debugPrint("Setting up Advance Tab")

        aframe = Tab(self.tabFrame, "Advanced", fname='advanced')
        aframe.config(relief=tk.RAISED, borderwidth=2, width=self.widthMain,
                      height=self.heightTab)
        self.tBarFrame.add(aframe)
        
        tk.Canvas(aframe, bd=0, highlightthickness=0, width=self.widthMain-4,
                  height=28).grid(row=1, column=1, columnspan=3)
        tk.Canvas(aframe, bd=0, highlightthickness=0, width=150,
                  height=self.heightTab-4).grid(row=1, column=1, rowspan=3)
              
        tk.Label(aframe, text="Select an Advanced Task to Launch").grid(row=1,
                                                                        columnspan=3,
                                                                        column=1,
                                                                        sticky=tk.W)
                                                            
        lbframe = tk.Frame(aframe, bd=2, relief=tk.SUNKEN)
        
        self.scrollbar = tk.Scrollbar(lbframe)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.advanceSelect = tk.Listbox(lbframe, bd=0, height=10,
                                    yscrollcommand=self.scrollbar.set)
        self.advanceSelect.bind('<<ListboxSelect>>', self.onAdvanceSelect)
        self.advanceSelect.pack()
        
        self.scrollbar.config(command=self.advanceSelect.yview)
        
        lbframe.grid(row=2, column=1, sticky=tk.W+tk.E+tk.N+tk.S, padx=2)
        
        for n in range(len(self.advanceList)):
            self.advanceSelect.insert(n, "{}: {}".format(n+1,
                                                     self.advanceList[n]['Name']))
        
        self.launchAdvanceButton = tk.Button(aframe, text="Launch",
                                      command=self.launchAdvance,)
        self.launchAdvanceButton.grid(row=3, column=1, columnspan=3)

        if self.disableLaunch:
          self.launchAdvanceButton.config(state=tk.DISABLED)

        self.advanceText = tk.Label(aframe, text="", width=40, height=11,
                              relief=tk.RAISED, justify=tk.LEFT, anchor=tk.NW)
        self.advanceText.grid(row=2, column=3, rowspan=2, sticky=tk.W+tk.E+tk.N,
                        padx=2)
                        
        self.advanceSelect.selection_set(0)
        self.onAdvanceSelect(None)
    
    def onAppSelect(self, *args):
        self.debugPrint("App select update")
        #self.debugPrint(args)
        self.appText.config(
                        text=self.appList[int(self.appSelect.curselection()[0])
                                          ]['Description'])
    
        # update buttons in self.launchFrame based on service or not
        if self.appList[int(self.appSelect.curselection()[0])]['Service']:
            self.launchFrame.pack_forget()
            self.SSRFrame.pack()
            if self.appList[int(self.appSelect.curselection()[0])].get('Autostart', 0):
                self.serviceButton.pack()
            else:
                self.serviceButton.pack_forget()
            if args[0] is not None:
                self.updateSSRButtons()
        else:
            self.SSRFrame.pack_forget()
            self.launchFrame.pack()
    
    def onAdvanceSelect(self, *args):
        self.debugPrint("Advnace select update")
        #self.debugPrint(args)
        self.advanceText.config(
                          text=self.advanceList[int(self.advanceSelect.curselection()[0])
                                            ]['Description'])
    
    def updateSSRButtons(self):
        """ Update buttons based on the state of the current selection in appList
        """
        # use status to find out if the service is currently running
        running = None
        if sys.platform == 'win32':
            pass
        else:
            # check using 'status'
            items = map(int, self.appSelect.curselection())
            if items:
                app = ["./{}".format(
                                     self.appList[int(self.appSelect.curselection()[0])]['FileName']
                                     )]
                if not self.appList[int(self.appSelect.curselection()[0])]['Args'] == "":
                    app.append(self.appList[int(self.appSelect.curselection()[0])]['Args'])

                app.append("status")

                self.debugPrint("Querying {}".format(app))
                output = subprocess.check_output(app, cwd=self.appList[int(self.appSelect.curselection()[0])]['CWD'])
                if output.find("PID") is not -1:
                    running = True
                elif output.find("not") is not -1:
                    running = False
                        
        if running:
            self.SSRFrame.children['start'].config(state=tk.DISABLED)
            self.SSRFrame.children['stop'].config(state=tk.ACTIVE)
            self.SSRFrame.children['restart'].config(state=tk.ACTIVE)
        elif not running:
            self.SSRFrame.children['start'].config(state=tk.ACTIVE)
            self.SSRFrame.children['stop'].config(state=tk.DISABLED)
            self.SSRFrame.children['restart'].config(state=tk.DISABLED)

        # if autostart find out if installed
        if self.appList[int(self.appSelect.curselection()[0])].get('Autostart', 0):
            installed = None
            if sys.platform == 'win32':
                pass
            elif sys.platform == 'darwin':
                # OSX auto start is diffrent so pass for now
                pass
            else:
                # check init.d and rc3.d
                if os.path.exists("/etc/init.d/{}".format(self.appList[int(self.appSelect.curselection()[0])]['InitScript'])):
                    # ok script is there is it setup in rc3.d
                    installed = False
                    for file in os.listdir("/etc/rc3.d/"):
                        if file.find(self.appList[int(self.appSelect.curselection()[0])]['InitScript']) is not -1:
                            installed = True
                else:
                    installed = False
                    
            if installed == True:
                self.serviceButton.config(state=tk.ACTIVE, text=self._autoStartText['disable'], command=lambda: self.autostart('disable'))
            elif installed == False:
                self.serviceButton.config(state=tk.ACTIVE, text=self._autoStartText['enable'], command=lambda: self.autostart('enable'))
            else:
                self.serviceButton.config(state=tk.DISABLED, text=self._autoStartText['enable'])

    def disableSSRButtons(self):
        self.SSRFrame.children['start'].config(state=tk.DISABLED)
        self.SSRFrame.children['stop'].config(state=tk.DISABLED)
        self.SSRFrame.children['restart'].config(state=tk.DISABLED)
        self.serviceButton.config(state=tk.DISABLED)
    
    def autostart(self, command=None):
        self.debugPrint("Configer autostart")
        if sys.platform == 'win32':
            pass
        elif sys.platform == 'darwin':
            # OSX auto start is diffrent so pass for now
            pass
        else:
            if command == 'enable':
                self.debugPrint("Setting up init.d script")
                self.disableSSRButtons()
                self.master.wait_window(PasswordDialog(self))
                # run update-rc.d {} remove (if there is an older script there)
                self.updateRCd('remove')
                # copy script to init.d dir
                src = (self.appList[int(self.appSelect.curselection()[0])]['CWD'] +
                       'init.d/' +
                       self.appList[int(self.appSelect.curselection()[0])]['InitScript']
                       )
                dst = ('/etc/init.d/' +
                       self.appList[int(self.appSelect.curselection()[0])]['InitScript']
                       )
                
                copyCommand = ['sudo', '-p','','-S',
                               'cp', src, dst
                               ]
                cproc = subprocess.Popen(copyCommand,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE
                                        )
                cproc.stdin.write(self.password+'\n')
                cproc.stdin.close()
                cproc.wait()
                chCommand = ['sudo', '-p','','-S',
                             'chmod', '+x', dst
                             ]
                chproc = subprocess.Popen(chCommand,
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE
                                          )
                chproc.stdin.write(self.password+'\n')
                chproc.stdin.close()
                chproc.wait()
                # run update-rc.d {} defualts
                self.updateRCd('defaults')
                self.master.after(500, self.updateSSRButtons)
    
            elif command == 'disable':
                self.debugPrint("Removing init.d script")
                self.disableSSRButtons()
                self.master.wait_window(PasswordDialog(self))
                # run update-rc.d {} remove
                self.updateRCd('remove')
                # rm script from /etc/init.d ???
                removeCommand = ['sudo', '-p','','-S',
                                 'rm', ('/etc/init.d/' + self.appList[int(self.appSelect.curselection()[0])]['InitScript'])
                                 ]

                rproc = subprocess.Popen(removeCommand,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE
                                        )
                rproc.stdin.write(self.password+'\n')
                rproc.stdin.close()
                rproc.wait()
                self.master.after(500, self.updateSSRButtons)
                

    def updateRCd(self, command):
        self.debugPrint("Calling updateRC.d with {}".format(command))
        updateRCCommand = ['sudo','-p','','-S',
                           'update-rc.d',
                           self.appList[int(self.appSelect.curselection()[0])]['InitScript']
                           ]
        proc = subprocess.Popen(updateRCCommand +[command],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE
                                )
        proc.stdin.write(self.password+'\n')
        proc.stdin.close()
        proc.wait()
                            

    def launch(self, command):
        items = map(int, self.appSelect.curselection())
        if items:
            app = ["./{}".format(
                 self.appList[int(self.appSelect.curselection()[0])]['FileName']
                                 )]
            if not self.appList[int(self.appSelect.curselection()[0])]['Args'] == "":
                app.append(self.appList[int(self.appSelect.curselection()[0])]['Args'])
        
            if self.debugArg:
                    app.append("-d")
        
            if command is not None and command is not 'launch':
                app.append(command)
            
            self.debugPrint("Launching {}".format(app))
            self.proc.append(subprocess.Popen(app, cwd=self.appList[int(self.appSelect.curselection()[0])]['CWD']))

            if command is not None and command is not 'launch':
                self.disableSSRButtons()
                if command == 'start':
                    self.master.after(2000, self.updateSSRButtons)
                else:
                    self.master.after(5000, self.updateSSRButtons)
    
        else:
            self.debugPrint("Nothing Selected to Launch")
                
    def launchAdvance(self):
        items = map(int, self.advanceSelect.curselection())
        if items:
            if items[0] == 0:
                self.manualZipUpdate()
        else:
            self.debugPrint("Nothing Selected to Launch")

    def readConfig(self):
        self.debugPrint("Reading Config")

        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self.configFileDefault))
        except:
            self.debugPrint("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self.configFile):
            self.debugPrint("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self.debugPrint("No Config Loaded, Quitting")
            sys.exit()
        
        self.debug = self.config.getboolean('Shared', 'debug')

        try:
            f = open(self.config.get('Update', 'versionfile'))
            self.currentVersion = f.read()
            f.close()
        except:
            pass
                
    def writeConfig(self):
        self.debugPrint("Writing Config")
        with open(self.configFile, 'wb') as configfile:
            self.config.write(configfile)

    def loadApps(self):
        self.debugPrint("Loading App List")
        try:
            with open(self.appFile, 'r') as f:
                read_data = f.read()
            f.closed
            
            self.appList = json.loads(read_data)['Apps']
            self.advanceList = json.loads(read_data)['Advanced']
        except IOError:
            self.debugPrint("Could Not Load AppList File")
            self.appList = [
                            {'id': 0,
                            'Name': 'Error',
                            'FileName': None,
                            'Args': '',
                            'Description': 'Error loading AppList file'
                            }]
            self.advanceList = [
                                {'id': 0,
                                'Name': 'Error',
                                'Description': 'Error loading AppList file'
                                }]
            self.disableLaunch = True

class PasswordDialog(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, )
        self.parent = parent
        position = self.parent.master.geometry().split("+")
        self.geometry("+{}+{}".format(
                                      int(position[1]
                                          )+self.parent.widthMain/4,
                                      int(position[2]
                                          )+self.parent.heightMain/4
                                      )
                      )
        if sys.platform == 'win32':
            tk.Label(self, text="Please enter Admin password").pack()
        else:
            tk.Label(self, text="Please enter root password").pack()
        self.entry = tk.Entry(self, show='*')
        self.entry.bind("<KeyRelease-Return>", self.StorePassEvent)
        self.entry.pack()
        self.button = tk.Button(self)
        self.button["text"] = "Submit"
        self.button["command"] = self.StorePass
        self.button.pack()
    
    def StorePassEvent(self, event):
        self.StorePass()
    
    def StorePass(self):
        self.parent.password = self.entry.get()
        self.destroy()

if __name__ == "__main__":
    app = LLAPLauncher()
    app.on_excute()

