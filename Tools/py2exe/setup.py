from distutils.core import setup
import py2exe

setup(windows=['../ConfigurationWizard/ConfigurationWizard.py'],
      console=['../MessagingBridge/MessageBridge.py'],
      data_files=[('', ['../ConfigurationWizard/ConfigurationWizard_defaults.cfg', '../LLAPDevices.json', '../MessagingBridge/MessageBridge.cfg', '../ConfigurationWizard/noun_80697_cc.gif'])],

      )
