# UpdateManager.py 
#  
#  Copyright (c) 2008 Canonical
#  
#  Author: Tollef Fog Heen <tfheen@err.no>
#          Emmet Hikory <persia@ubuntu.com>
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
from UpdateManager.GtkProgress import GtkFetchProgress
import hildon

import pygtk
pygtk.require('2.0')
import gtk

import apt
import apt_pkg
from gettext import gettext as _

import logging
import time
import os

# actions for "invoke_manager"
(INSTALL, UPDATE) = range(2)

# DistUpgrade.DistUpgradeViewGtk.GtkInstallProgressAdapter is better,
# but requires more effort, and vte.  This is a simpler implementation.

class GtkInstallProgress(apt.progress.InstallProgress):

  def __init__(self,parent, summary="", descr=""):
    apt.progress.InstallProgress.__init__(self)
    self.progress = parent.progressbar_cache
    self.summary = parent.label_fetch_summary
    self.status = parent.label_fetch_status
    self.progress = parent.progressbar_fetch
    self.window_fetch = parent.window_fetch
    self.window_fetch.set_transient_for(parent.window_main)
    self.window_fetch.realize()
    self.window_fetch.window.set_functions(gtk.gdk.FUNC_MOVE)
    if self.summary != "":
      self.summary.set_markup("<big><b>%s</b></big> \n\n%s" %
                              (summary, descr))

  def startUpdate(self):
    self.progress.set_fraction(0.0)
    self.status
    self.progress.set_text(" ")
    self.env = ["DEBIAN_FRONTEND=noninteractive", 
                "APT_LISTCHANGES_FRONTEND=none"]
    self.start_time = 0.0
    self.time_ui = 0.0
    self.last_activity = 0.0
    self.window_fetch.show()

  def statusChange(self, pkg, percent, status):
    if self.start_time == 0.0:
      self.start_time = time.time()
    self.progress.set_fraction(float(percent)/100.0)
    if percent > 1.0:
      self.last_activity = time.time()
      self.activity_timeout_reported = False
      delta = self.last_activity - self.start_time
      time_per_percent = (float(delta)/percent)
      eta = (100.0 - percent) * time_per_percent
      if eta > 61.0 and eta < (60*60*24*2):
        self.progress.set_text(_("About %s remaining") % FuzzyTimeToStr(eta))
      else:
        self.progress.set_text(" ")

  def updateInterface(self):
    try:
      apt.progress.InstallProgress.updateInterface(self)
    except ValueError, e:
      logging.error("got ValueError from InstallProgress.updateInterface. Line was '%s' (%s)" % (self.read, e))
      self.read = ""
      if self.start_time == 0.0:
        self.progress.pulse()
        time.sleep(0.2)
      if self.last_activity > 0 and \
          (self.last_activity + self.TIMEOUT_TERMINAL_ACTIVITY) < time.time():
        if not self.activity_timeout_reported:
          logging.warning("no activity on terminal for %s seconds (%s)" % (self.TIMEOUT_TERMINAL_ACTIVITY, self.label_status.get_text()))
          self.activity_timeout_reported = True
      while gtk.events_pending():
        gtk.main_iteration()
      time.sleep(0.02)

  def finishUpdate(self):
    self.window_fetch.hide()

class UpdateManagerHildon(UpdateManager):

  def __init__(self, datadir):
      UpdateManager.__init__(self, datadir)
      self.program = hildon.Program()
      self.program.__init__()
        
      self.window = hildon.Window()
      self.window.set_title("PyGlade")
      self.program.add_window(self.window)
      print dir(self.glade)
      for widget in [ "window_main", "dialog_release_notes", "window_fetch", \
                          "dialog_manual_update", "dialog_cacheprogress", \
                          "dialog_dist_upgrade" ]:
          self.glade.get_widget(widget).reparent(self.window)


  def run_synaptic(self, id, action, lock):
    try:
      apt_pkg.PkgSystemUnLock()
    except SystemError:
      pass

    fprogress = GtkFetchProgress(self, _("Downloading Package Information"),
                _("The repositories will be checked for new, removed, or "
                  "updated software packages"))
    iprogress = GtkInstallProgress(self, _("Downloading Package Updates"),
                _("The selected package updates are being downloaded and "
                  "installed on the system"))
    if action == INSTALL:
      self.cache.commit(fprogress, iprogress)
    elif action == UPDATE:
      self.cache.update(fprogress)
    else:
      print _("run_synaptic called with unknown action")
      sys.exit(1)
    lock.release()

