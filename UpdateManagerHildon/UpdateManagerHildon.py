# UpdateManager.py 
#  
#  Copyright (c) 2008 Canonical
#  
#  Author: Tollef Fog Heen <tfheen@err.no>
#          Emmet Hikory <persia@ubuntu.com>
#          Michael Vogt <mvo@ubuntu.com>
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

from UpdateManager.UpdateManager import UpdateManager
import hildon

import pygtk
pygtk.require('2.0')
import gtk

import apt
import apt_pkg
from gettext import gettext as _
from UpdateManager.Core.utils import *

import logging
import time
import os

# actions for "invoke_manager"
(INSTALL, UPDATE) = range(2)

from DistUpgrade.DistUpgradeViewGtk import DistUpgradeViewGtk, GtkFetchProgressAdapter, GtkInstallProgressAdapter
from DistUpgrade.DistUpgradeView import (STEP_PREPARE, 
                                         STEP_MODIFY_SOURCES, 
                                         STEP_FETCH, 
                                         STEP_INSTALL, 
                                         STEP_CLEANUP, 
                                         STEP_REBOOT,
                                         STEP_N)

class HildonFetchProgress(GtkFetchProgressAdapter):
  def __init__(self, parent, header, msg):
    GtkFetchProgressAdapter.__init__(self, parent)
    # hide all steps
    for i in range(1,STEP_N):
      parent.hideStep(i)
    parent.label_title.set_markup("<b><big>%s</big></b>" % header)
  def start(self):
    GtkFetchProgressAdapter.start(self)
    # this is only needed when a InstallProgressAdapter is used
    # in addition to the FetchProgress one - they share the 
    # same parent
    self.parent.setStep(STEP_FETCH)

class HildonInstallProgressAdapter(GtkInstallProgressAdapter):
  def __init__(self, parent, header, msg):
    GtkInstallProgressAdapter.__init__(self, parent)
    # hide step not relevant
    for i in (STEP_PREPARE, 
              STEP_MODIFY_SOURCES, 
              STEP_CLEANUP, 
              STEP_REBOOT):
      parent.hideStep(i)
    # and show only those two
    for i in (STEP_FETCH, 
                STEP_INSTALL):
        parent.showStep(i)
    parent.label_title.set_markup("<b><big>%s</big></b>" % header)
  def startUpdate(self):
    GtkInstallProgressAdapter.startUpdate(self)
    self.parent.setStep(STEP_INSTALL)

class UpdateManagerHildon(UpdateManager):

  def __init__(self, datadir):
      UpdateManager.__init__(self, datadir)
      self.program = hildon.Program()
      self.program.__init__()

      self.window = hildon.Window()
      self.window.set_title("PyGlade")
      self.program.add_window(self.window)
      #print dir(self.glade)
      for widget in [ "window_main", "dialog_release_notes", "window_fetch", 
                      "dialog_manual_update", "dialog_cacheprogress", 
                      "dialog_dist_upgrade" ]:
          self.glade.get_widget(widget).reparent(self.window)
      self.view = None

  # FIXME: below is still too much duplicated code m'kay
  def invoke_manager(self, action):
    # don't display apt-listchanges, we already showed the changelog
    os.environ["APT_LISTCHANGES_FRONTEND"]="none"
    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
    # Do not suspend during the update process
    (dev, cookie) = inhibit_sleep()
    # set window to insensitive
    self.window_main.set_sensitive(False)
    self.window_main.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))

    self.run_synaptic(None, action, None)

    s = _("Reading package information")
    self.label_cache_progress_title.set_label("<b><big>%s</big></b>" % s)
    self.fillstore()

    # Allow suspend after synaptic is finished
    if cookie != False:
        allow_sleep(dev, cookie)
    self.window_main.set_sensitive(True)
    self.window_main.window.set_cursor(None)
    

  def run_synaptic(self, id, action, lock):
    try:
      apt_pkg.PkgSystemUnLock()
    except SystemError:
      pass
    
    if self.view == None:
      self.view = DistUpgradeViewGtk("/usr/share/update-manager")
      self.view.window_main.set_transient_for(self.window_main)

    fprogress = HildonFetchProgress(self.view, 
                _("Downloading Package Information"),
                _("The repositories are being checked for new, removed, "
                  "or updated software packages"))
    self.view.window_main.show()

    # FIXME: add error handling (commit() and update() both can
    #        throw SystemErrors 
    if action == INSTALL:
      iprogress = HildonInstallProgressAdapter(self.view, 
                    _("Downloading Package Updates"),
                    _("The selected package updates are being downloaded and "
                      "installed on the system"))
      self.cache.commit(fprogress, iprogress)
    elif action == UPDATE:
      self.cache.update(fprogress)
    else:
      print _("run_synaptic called with unknown action")
      return False
    self.view.window_main.hide()
    #lock.release()

  def check_auto_update(self): 
    pass
