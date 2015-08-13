""" py2Exe Build script

    Author: Matt Lloyd
    Copyright 2015 Ciseco Ltd.

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

from distutils.core import setup
import py2exe

setup(windows=['../ConfigurationWizard/ConfigurationWizard.py'],
      console=['../MessagingBridge/MessageBridge.py'],
      data_files=[('', ['../ConfigurationWizard/ConfigurationWizard_defaults.cfg', '../LLAPDevices.json', '../MessagingBridge/MessageBridge.cfg'])],

      )
