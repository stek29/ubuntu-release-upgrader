# setup.py - distutils module for Computer Janitor
# Copyright (C) 2008  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from distutils.core import setup
from DistUtilsExtra.command import *
import os

import computerjanitor

disabled = []

def plugins():
    return [os.path.join('plugins', name)
            for name in os.listdir('plugins')
            if name.endswith('_plugin.py') and name not in disabled]

setup(name='computer-janitor',
      version=computerjanitor.VERSION,
      description="Clean up a system so it's more like a freshly "
                  "installed one",
      author='Lars Wirzenius',
      author_email='lars@ubuntu.com',
      packages=['computerjanitor'],
      scripts=['computer-janitor'],
      data_files=[('share/man/man8', ['computer-janitor.8', 
                                      'computer-janitor-gtk.8']),
                  ('share/computer-janitor/plugins', plugins())],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" :  build_help.build_help,
                   "build_icons" :  build_icons.build_icons }
     )
