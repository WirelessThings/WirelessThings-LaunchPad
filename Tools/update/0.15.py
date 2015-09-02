#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, ConfigParser

class PostUpdate():
    # TODO: Error treatments messages (should print?)
    def readConfig(self, configFile, configFileDefault):
        self.config = ConfigParser.SafeConfigParser()

        # load defaults
        try:
            self.config.readfp(open(configFileDefault))
        except:
            pass

        # read the user config file
        if not self.config.read(configFile):
            pass

    def writeConfig(self, configFile):
        with open(configFile, 'wb') as _configFile:
            self.config.write(_configFile)

    # if already exists a config file, update it with the new changes on defaults,
    # otherwise, they will be created when the program be closed for the first time
    # TODO: This could be changed to add or remove specific sections or options on the users config
    def checkExistingConfigFile(self, filename):
        configFile = "./{0}/{0}.cfg".format(filename)
        if os.path.exists(configFile)
            configFileDefault = "./{0}/{0}_defaults.cfg".format(filename)
            self.readConfig(configFile, configFileDefault)
            self.writeConfig(configFile)

    def on_execute(self):
        self.checkExistingConfigFile("ConfigurationWizard")
        self.checkExistingConfigFile("MessageBridge")
        self.checkExistingConfigFile("LaunchPad")

if __name__ == "__main__":
    app = PostUpdate()
    app.on_execute()
