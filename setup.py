#!/usr/bin/env python

from distutils.core import setup, Extension
import glob
import os
from DistUtilsExtra.command import *

setup(name='update-manager',
      version='0.56',
      ext_modules=[Extension('UpdateManager/fdsend',
                             ['UpdateManager/fdsend/fdsend.c'])],
      packages=[
                'UpdateManager',
                'UpdateManager.Common',
                'UpdateManager.Core',
                'UpdateManagerHildon',
                'DistUpgrade'
                ],
      scripts=[
               'update-manager', "do-release-upgrade", "update-manager-hildon"
               ],
      data_files=[
                  ('share/update-manager/glade',
                   glob.glob("data/glade/*.glade")+
                   glob.glob("DistUpgrade/*.glade")
                  ),
                  ('share/update-manager/',
                   glob.glob("DistUpgrade/*.cfg")
                  ),
                  ('share/man/man8',
                   glob.glob('data/*.8')
                  ),
                  ('../etc/update-manager/',
                   ['data/release-upgrades',
                    'data/meta-release']),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" :  build_help.build_help,
                   "build_icons" :  build_icons.build_icons }
      )
