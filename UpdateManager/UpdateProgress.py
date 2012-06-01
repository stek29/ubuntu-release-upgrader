# UpdatProgress.py
#  
#  Copyright (c) 2004-2012 Canonical
#                2004 Michiel Sikkes
#                2005 Martin Willemoes Hansen
#                2010 Mohamed Amine IL Idrissi
#  
#  Author: Michiel Sikkes <michiel@eyesopened.nl>
#          Michael Vogt <mvo@debian.org>
#          Martin Willemoes Hansen <mwh@sysrq.dk>
#          Mohamed Amine IL Idrissi <ilidrissiamine@gmail.com>
#          Alex Launi <alex.launi@canonical.com>
#          Michael Terry <michael.terry@canonical.com>
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU General Public License as 
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

from __future__ import absolute_import, print_function

from gi.repository import Gtk
from gi.repository import GLib

import warnings
warnings.filterwarnings("ignore", "Accessed deprecated property", DeprecationWarning)

import os
import sys

from .backend import get_backend

from gettext import gettext as _
from gettext import ngettext

from UpdateManager.UpdateManager import UpdateManager
from .Core.utils import (inhibit_sleep,
                         allow_sleep)

class UpdateProgress(object):

  def __init__(self, datadir, options):
    self.datadir = datadir
    self.options = options

    # Used for inhibiting power management
    self.sleep_cookie = None
    self.sleep_dev = None

    # get the install backend
    self.install_backend = get_backend(None)
    self.install_backend.connect("action-done", self._on_backend_done)

  def invoke_manager(self):
    # don't display apt-listchanges
    os.environ["APT_LISTCHANGES_FRONTEND"]="none"

    # Do not suspend during the update process
    (self.sleep_dev, self.sleep_cookie) = inhibit_sleep()

    self.install_backend.update()

  def _on_backend_done(self, backend, action, authorized, success):
    # Allow suspend after synaptic is finished
    if self.sleep_cookie:
      allow_sleep(self.sleep_dev, self.sleep_cookie)
      self.sleep_cookie = self.sleep_dev = None

    # Either launch main dialog and continue or quit altogether
    if success:
      app = UpdateManager(self.datadir, self.options)
      # Run app.main at idle time so the progress dialog can close before we
      # do lengthy recalculation in app.main
      GLib.idle_add(app.main)
    else:
      sys.exit(0)

  def main(self):
    self.invoke_manager()
