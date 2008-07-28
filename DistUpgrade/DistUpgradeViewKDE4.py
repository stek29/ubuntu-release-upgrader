# DistUpgradeViewKDE.py 
#  
#  Copyright (c) 2007 Canonical Ltd
#  
#  Author: Jonathan Riddell <jriddell@ubuntu.com>
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

import sys
import logging
import time
import subprocess
import traceback
import tempfile

import apt
import apt_pkg
import os
import shutil

import pty

from DistUpgradeApport import *

from DistUpgradeController import DistUpgradeController
from DistUpgradeView import DistUpgradeView, FuzzyTimeToStr, InstallProgress, FetchProgress
#FIXME import bits here

import select
import gettext
from gettext import gettext as gett

def _(str):
    return unicode(gett(str), 'UTF-8')

def utf8(str):
  if isinstance(str, unicode):
      return str
  return unicode(str, 'UTF-8')

class KDECdromProgressAdapter(apt.progress.CdromProgress):
    """ Report the cdrom add progress """
    def __init__(self, parent):
        self.status = parent.window_main.label_status
        self.progressbar = parent.window_main.progressbar_cache
        self.parent = parent

    def update(self, text, step):
        """ update is called regularly so that the gui can be redrawn """
        if text:
          self.status.setText(text)
        self.progressbar.setValue(step/float(self.totalSteps))
        KApplication.processEvents()

    def askCdromName(self):
        return (False, "")

    def changeCdrom(self):
        return False

class KDEOpProgress(apt.progress.OpProgress):
  """ methods on the progress bar """
  def __init__(self, progressbar, progressbar_label):
      self.progressbar = progressbar
      self.progressbar_label = progressbar_label
      #self.progressbar.set_pulse_step(0.01)
      #self.progressbar.pulse()

  def update(self, percent):
      #if percent > 99:
      #    self.progressbar.set_fraction(1)
      #else:
      #    self.progressbar.pulse()
      #self.progressbar.set_fraction(percent/100.0)
      self.progressbar.setValue(percent)
      QApplication.processEvents()

  def done(self):
      self.progressbar_label.setText("")

class KDEFetchProgressAdapter(FetchProgress):
    """ methods for updating the progress bar while fetching packages """
    # FIXME: we really should have some sort of "we are at step"
    # xy in the gui
    # FIXME2: we need to thing about mediaCheck here too
    def __init__(self, parent):
        FetchProgress.__init__(self)
        # if this is set to false the download will cancel
        self.status = parent.window_main.label_status
        self.progress = parent.window_main.progressbar_cache
        self.parent = parent

    def mediaChange(self, medium, drive):
      msg = _("Please insert '%s' into the drive '%s'") % (medium,drive)
      change = QMessageBox.question(self.parent.window_main, _("Media Change"), msg, QMessageBox.Ok, QMessageBox.Cancel)
      if change == QMessageBox.Ok:
        return True
      return False

    def start(self):
        #self.progress.show()
        self.progress.setValue(0)
        self.status.show()

    def stop(self):
        self.parent.window_main.progress_text.setText("  ")
        self.status.setText(_("Fetching is complete"))

    def pulse(self):
        """ we don't have a mainloop in this application, we just call processEvents here and elsewhere"""
        # FIXME: move the status_str and progress_str into python-apt
        # (python-apt need i18n first for this)
        FetchProgress.pulse(self)
        self.progress.setProgress(self.percent)
        currentItem = self.currentItems + 1
        if currentItem > self.totalItems:
            currentItem = self.totalItems

        if self.currentCPS > 0:
            self.status.setText(_("Fetching file %li of %li at %sb/s") % (currentItem, self.totalItems, apt_pkg.SizeToStr(self.currentCPS)))
            self.parent.window_main.progress_text.setText("<i>" + _("About %s remaining") % unicode(FuzzyTimeToStr(self.eta), 'utf-8') + "</i>")
        else:
            self.status.setText(_("Fetching file %li of %li") % (currentItem, self.totalItems))
            self.parent.window_main.progress_text.setText("  ")

        QApplication.processEvents()
        return True

# inherit from the class created in window_main.ui
# to add the handler for closing the window
class UpgraderMainWindow(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        ##FIXMEuic.loadUi("%s/window_main.ui" % UIDIR, self)
        uic.loadUi("window_main.ui", self)

    def setParent(self, parentRef):
        self.parent = parentRef

    def closeEvent(self, event):
        close = self.parent.on_window_main_delete_event()
        if close:
            event.accept()#FIXME needs ignore?
        else:
            event.ignore()

class DistUpgradeViewKDE4(DistUpgradeView):
    """KDE frontend of the distUpgrade tool"""
    def __init__(self, datadir=None, logdir=None):
        if not datadir:
          localedir=os.path.join(os.getcwd(),"mo")
        else:
          localedir="/usr/share/locale/update-manager"

        # FIXME: i18n must be somewhere relative do this dir
        try:
          gettext.bindtextdomain("update-manager", localedir)
          gettext.textdomain("update-manager")
        except Exception, e:
          logging.warning("Error setting locales (%s)" % e)

        #about = KAboutData("adept_manager","Upgrader","0.1","Dist Upgrade Tool for Kubuntu",KAboutData.License_GPL,"(c) 2007 Canonical Ltd",
        #"http://wiki.kubuntu.org/KubuntuUpdateManager", "jriddell@ubuntu.com")
        #about.addAuthor("Jonathan Riddell", None,"jriddell@ubuntu.com")
        #about.addAuthor("Michael Vogt", None,"michael.vogt@ubuntu.com")
        #KCmdLineArgs.init(["./dist-upgrade.py"],about)

        #self.app = KApplication()
        self.app = QApplication(["update-manager"])

        self.window_main = UpgraderMainWindow()
        self.window_main.setParent(self)
        self.window_main.show()

        self.prev_step = 0 # keep a record of the latest step

        self._opCacheProgress = KDEOpProgress(self.window_main.progressbar_cache, self.window_main.progress_text)
        self._fetchProgress = KDEFetchProgressAdapter(self)
        self._cdromProgress = KDECdromProgressAdapter(self)

        """
        self._installProgress = KDEInstallProgressAdapter(self)

        # reasonable fault handler
        sys.excepthook = self._handleException

        ###self.window_main.showTerminalButton.setEnabled(False)
        self.app.connect(self.window_main.showTerminalButton, SIGNAL("clicked()"), self.showTerminal)

        #kdesu requires us to copy the xauthority file before it removes it when Adept is killed
        copyXauth = tempfile.mktemp("", "adept")
        if 'XAUTHORITY' in os.environ and os.environ['XAUTHORITY'] != copyXauth:
            shutil.copy(os.environ['XAUTHORITY'], copyXauth)
            os.environ["XAUTHORITY"] = copyXauth

        # Note that with kdesudo this needs --nonewdcop
        ## create a new DCOP-Client:
        #client = DCOPClient()
        ## connect the client to the local DCOP-server:
        #client.attach()

        #for qcstring_app in client.registeredApplications():
        #    app = str(qcstring_app)
        #    if app.startswith("adept"): 
        #        adept = DCOPApp(qcstring_app, client)
        #        adeptInterface = adept.object("MainApplication-Interface")
        #        adeptInterface.quit()

        # This works just as well
        subprocess.call(["killall", "adept_manager"])
        subprocess.call(["killall", "adept_updater"])

        # init gettext
        gettext.bindtextdomain("update-manager",localedir)
        gettext.textdomain("update-manager")
        self.translate_widget_children()
        self.window_main.label_title.setText(self.window_main.label_title.text().replace("Ubuntu", "Kubuntu"))

        # setup terminal text in hidden by default spot
        self.window_main.konsole_frame.hide()
        self.konsole_frame_layout = QHBoxLayout(self.window_main.konsole_frame)
        self.window_main.konsole_frame.setMinimumSize(600, 400)
        self.terminal_text = DumbTerminal(self._installProgress, 
                                          self.window_main.konsole_frame)
        self.konsole_frame_layout.addWidget(self.terminal_text)
        self.terminal_text.show()

        # for some reason we need to start the main loop to get everything displayed
        # this app mostly works with processEvents but run main loop briefly to keep it happily displaying all widgets
        QTimer.singleShot(10, self.exitMainLoop)
        """
        self.app.exec_()

    def on_window_main_delete_event(self):
        #FIXME make this user friendly
        text = _("""<b><big>Cancel the running upgrade?</big></b>

The system could be in an unusable state if you cancel the upgrade. You are strongly advised to resume the upgrade.""")
        text = text.replace("\n", "<br />")
        cancel = QMessageBox.warning(self.window_main, _("Cancel Upgrade?"), text, QMessageBox.Yes, QMessageBox.No)
        if cancel == QMessageBox.Yes:
            return True
        return False
