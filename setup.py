#!/usr/bin/env python

from distutils.core import setup, Extension
import glob
import os
from DistUtilsExtra.distutils_extra import build_extra, build_l10n, \
                                           build_icons, build_help

setup(name='update-manager',
      version='0.42.2',
#      ext_modules=[Extension('fdsend', ['fdsend/fdsend.c'])],
      packages=[
                'UpdateManager',
                'UpdateManager.Common',
                'UpdateManager.Core',
                'DistUpgrade'
                ],
      scripts=[
               'update-manager', "do-release-upgrade"
               ],
      data_files=[
                  ('share/update-manager/glade',
                   glob.glob("data/glade/*.glade")+
                   glob.glob("DistUpgrade/*.glade")
                  ),
                  ('share/update-manager/',
                   glob.glob("DistUpgrade/*.cfg")
                  ),
                  ],
      cmdclass = { "build" : build_extra,
                   "build_l10n" :  build_l10n,
                   "build_help" :  build_help,
                   "build_icons" :  build_icons }
     )
