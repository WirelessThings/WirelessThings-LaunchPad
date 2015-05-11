from distutils.core import setup
import py2exe

setup(windows=['../LLAPConfigMeUI/LLAPConfigMe.py'],
      console=['../LLAPServer/LLAPServer.py'],
      data_files=[('', ['../LLAPConfigMeUI/LLAPCM_defaults.cfg', '../LLAPDevices.json', '../LLAPServer/LLAPServer.cfg'])],

      )