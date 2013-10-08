#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Wireless Inventors Kit Tab Class
    Copyright (c) 2013 Ciseco Ltd.
    
    Tab Helper's originaly written by Sunjay Varma - www.sunjay-varma.com
    and Licensed under the MIT License
    Source: http://code.activestate.com/recipes/577261-python-tkinter-tabs/
    
    Author's: Sunjay Varma, Matt Lloyd
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    
    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.
    
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
    
"""
import Tkinter as tk

# a base tab class
class Tab(tk.Frame):
    def __init__(self, master, name, fname):
        tk.Frame.__init__(self, master, name=fname)
        self.tab_name = name

# the bulk of the logic is in the actual tab bar
class TabBar(tk.Frame):
    def __init__(self, master=None, init_name=None, fname=None):
        tk.Frame.__init__(self, master, name=fname)
        self.tabs = {}
        self.buttons = {}
        self.current_tab = None
        self.init_name = init_name
    
    def show(self):
        self.pack(side=tk.TOP, expand=tk.YES, fill=tk.X)
        self.switch_tab(self.init_name or self.tabs.keys()[-1])# switch the tab to the first tab
    
    def add(self, tab):
        tab.pack_forget()									# hide the tab on init
        
        self.tabs[tab.tab_name] = tab						# add it to the list of tabs
        b = tk.Button(self, text=tab.tab_name, relief=tk.RAISED,	# basic button stuff
                   command=(lambda name=tab.tab_name: self.switch_tab(name)))	# set the command to switch tabs
        b.pack(side=tk.LEFT)											 	# pack the buttont to the left mose of self
        self.buttons[tab.tab_name] = b											# add it to the list of buttons
    
    def delete(self, tabname):
        
        if tabname == self.current_tab:
            self.current_tab = None
            self.tabs[tabname].pack_forget()
            del self.tabs[tabname]
            self.switch_tab(self.tabs.keys()[0])
        
        else: del self.tabs[tabname]
        
        self.buttons[tabname].pack_forget()
        del self.buttons[tabname]
    
    
    def switch_tab(self, name):
        if self.current_tab:
            self.buttons[self.current_tab].config(relief=tk.RAISED)
            self.tabs[self.current_tab].pack_forget()			# hide the current tab
        self.tabs[name].pack(side=tk.BOTTOM)							# add the new tab to the display
        self.current_tab = name									# set the current tab to itself
        
        self.buttons[name].config(relief=tk.SUNKEN)					# set it to the selected style