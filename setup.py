#!/usr/bin/env python

from distutils.core import setup
import glob
import os

from DistUtilsExtra.command import (
    build_extra, build_i18n, build_help, build_icons)


disabled = []

def plugins():
    return []
    return [os.path.join('janitor/plugincore/plugins', name)
            for name in os.listdir('janitor/plugincore/plugins')
            if name.endswith('_plugin.py') and name not in disabled]

setup(name='update-manager',
      version='0.56',
      packages=[
                'UpdateManager',
                'UpdateManager.backend',
                'UpdateManager.Core',
                'UpdateManagerText',
                'DistUpgrade',
                'janitor',
                ],
      package_dir={
                   '': '.',
                   'janitor.plugincore': 'janitor/plugincore',
                  },
      scripts=[
               'update-manager', 
               'ubuntu-support-status', 
               'update-manager-text', 
               "do-release-upgrade", 
               "kubuntu-devel-release-upgrade", 
               "check-new-release-gtk",
               ],
      data_files=[
                  ('share/update-manager/gtkbuilder',
                   glob.glob("data/gtkbuilder/*.ui")+
                   glob.glob("DistUpgrade/*.ui")
                  ),
                  ('share/update-manager/',
                   glob.glob("DistUpgrade/*.cfg")+
                   glob.glob("UpdateManager/*.ui")
                  ),
                  ('share/man/man8',
                   glob.glob('data/*.8')
                  ),
                  ('share/GConf/gsettings/',
                   ['data/update-manager.convert']),
                  ('../etc/update-manager/',
                   ['data/release-upgrades', 'data/meta-release']),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" :  build_help.build_help,
                   "build_icons" :  build_icons.build_icons }
      )
