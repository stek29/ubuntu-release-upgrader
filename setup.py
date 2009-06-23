#!/usr/bin/env python

from distutils.core import setup, Extension
import glob
import os
from DistUtilsExtra.command import *


disabled = []

def plugins():
    return [os.path.join('Janitor/plugins', name)
            for name in os.listdir('Janitor/plugins')
            if name.endswith('_plugin.py') and name not in disabled]

def profiles():
    profiles = []
    # FIXME: ship with a small collection of profiles for now
    #for d in os.listdir("AutoUpgradeTester/profile/"):
    for d in ["server", "ubuntu", "kubuntu", "main-all", "lts-server"]:
        base="AutoUpgradeTester/profile/"
        cfgs = [f for f in glob.glob("%s/%s/*" % (base,d)) if os.path.isfile(f)]
        profiles.append(("share/auto-upgrade-tester/profiles/"+d,cfgs))
    return profiles

setup(name='update-manager',
      version='0.56',
      ext_modules=[Extension('UpdateManager/fdsend',
                             ['UpdateManager/fdsend/fdsend.c'])],
      packages=[
                'UpdateManager',
                'UpdateManager.Core',
                'UpdateManagerHildon',
                'UpdateManagerText',
                'DistUpgrade',
                'computerjanitor',
                'AutoUpgradeTester',
                ],
      package_dir={
                   '': '.',
                   'computerjanitor': 'Janitor/computerjanitor',
                  },
      scripts=[
               'update-manager', 
               'update-manager-text', 
               "do-release-upgrade", 
               "update-manager-hildon",
               "check-new-release",
               "AutoUpgradeTester/auto-upgrade-tester",
               ],
      data_files=[
                  ('share/update-manager/glade',
                   glob.glob("data/glade/*.glade")+
                   glob.glob("DistUpgrade/*.glade")
                  ),
                  ('share/update-manager/',
                   glob.glob("DistUpgrade/*.cfg")+
                   glob.glob("UpdateManager/*.ui")
                  ),
                  ('share/man/man8',
                   glob.glob('data/*.8')
                  ),
                  ('../etc/update-manager/',
                   ['data/release-upgrades',
                    'data/meta-release']),
                  ('share/computerjanitor/plugins',
                   plugins()),
                  ]+profiles(),
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" :  build_help.build_help,
                   "build_icons" :  build_icons.build_icons }
      )
