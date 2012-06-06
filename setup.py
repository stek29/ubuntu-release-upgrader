#!/usr/bin/env python

from distutils.core import setup
import glob
import os

from DistUtilsExtra.command import (
    build_extra, build_i18n)

setup(name='ubuntu-release-upgrader',
      packages=[
                'DistUpgrade',
                ],
      package_dir={
                   '': '.',
                  },
      scripts=[
               "do-release-upgrade", 
               "kubuntu-devel-release-upgrade", 
               "check-new-release-gtk",
               ],
      data_files=[
                  ('share/ubuntu-release-upgrader/gtkbuilder',
                   glob.glob("data/gtkbuilder/*.ui")+
                   glob.glob("DistUpgrade/*.ui")
                  ),
                  ('share/ubuntu-release-upgrader/',
                   glob.glob("DistUpgrade/*.cfg")+
                   glob.glob("UpdateManager/*.ui")
                  ),
                  ('share/man/man8',
                   glob.glob('data/*.8')
                  ),
                  ('../etc/ubuntu-release-upgrader/',
                   ['data/release-upgrades', 'data/meta-release']),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n }
      )
