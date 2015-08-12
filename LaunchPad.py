#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" LaunchPad
    Quick Wrapper to move us into the LaunchPad/ directory

    Author: Matt Lloyd
    Copyright 2014 Ciseco Ltd.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
    
"""
import os
import sys
import inspect
args = sys.argv[:]
args[0] = 'LaunchPad.py'
args.insert(0, sys.executable)
if sys.platform == 'win32':
    args = ['"%s"' % arg for arg in args]

os.chdir(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + '/LaunchPad/')
os.execv(sys.executable, args)
