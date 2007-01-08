from qt import *
from kdeui import *
from kdecore import *

import sys
import logging
import time
import subprocess

import apt
import apt_pkg
import os

from DistUpgradeControler import DistUpgradeControler
from DistUpgradeView import DistUpgradeView, FuzzyTimeToStr, estimatedDownloadTime
from window_main import window_main
from dialog_error import dialog_error

import gettext
from gettext import gettext as _

def utf8(str):
  return unicode(str, 'latin1').encode('utf-8')

class KDEOpProgress(apt.progress.OpProgress):
  def __init__(self, progressbar):
      self.progressbar = progressbar
      #self.progressbar.set_pulse_step(0.01)
      #self.progressbar.pulse()

  def update(self, percent):
      #if percent > 99:
      #    self.progressbar.set_fraction(1)
      #else:
      #    self.progressbar.pulse()
      #self.progressbar.set_fraction(percent/100.0)
      self.progressbar.setProgress(percent)
      KApplication.kApplication().processEvents()

  def done(self):
      pass
      ##FIXMEself.progressbar.set_text(" ")

class KDEFetchProgressAdapter(apt.progress.FetchProgress):
    # FIXME: we really should have some sort of "we are at step"
    # xy in the gui
    # FIXME2: we need to thing about mediaCheck here too
    def __init__(self, parent):
        # if this is set to false the download will cancel
        self.status = parent.window_main.label_status
        self.progress = parent.window_main.progressbar_cache
        self.parent = parent
    def mediaChange(self, medium, drive):
      ##FIXME
      #print "mediaChange %s %s" % (medium, drive)
      msg = _("Please insert '%s' into the drive '%s'") % (medium,drive)
      dialog = gtk.MessageDialog(parent=self.parent.window_main,
                                 flags=gtk.DIALOG_MODAL,
                                 type=gtk.MESSAGE_QUESTION,
                                 buttons=gtk.BUTTONS_OK_CANCEL)
      dialog.set_markup(msg)
      res = dialog.run()
      #print res
      dialog.destroy()
      if  res == gtk.RESPONSE_OK:
        return True
      return False
    def start(self):
        #self.progress.show()
        self.progress.setProgress(0)
        self.status.show()
    def stop(self):
        self.parent.window_main.progress_text.setText("  ")
        self.status.setText(_("Fetching is complete"))
    def pulse(self):
        # FIXME: move the status_str and progress_str into python-apt
        # (python-apt need i18n first for this)
        apt.progress.FetchProgress.pulse(self)
        self.progress.setProgress(self.percent)
        ##FIXMEself.progress.setProgress(self.percent/100.0)
        currentItem = self.currentItems + 1
        if currentItem > self.totalItems:
            currentItem = self.totalItems

        if self.currentCPS > 0:
            self.status.setText(_("Fetching file %li of %li at %s/s") % (currentItem, self.totalItems, apt_pkg.SizeToStr(self.currentCPS)))
            self.parent.window_mainm.progress_text.setText("<i>" + _("About %s remaining") % FuzzyTimeToStr(self.eta) + "</i>")
        else:
            self.status.setText(_("Fetching file %li of %li") % (currentItem, self.totalItems))
            self.parent.window_main.progress_text.setText("  ")

        KApplication.kApplication().processEvents()
        return True


class DistUpgradeViewKDE(DistUpgradeView):
    "KDE frontend of the distUpgrade tool "
    def __init__(self, datadir=None):
        print "DistUpgradeViewKDE init()"
        if not datadir:
          localedir=os.path.join(os.getcwd(),"mo")
        else:
          localedir="/usr/share/locale/update-manager"

        # FIXME: i18n must be somewhere relative do this dir
        try:
          bindtextdomain("update-manager", localedir)
          gettext.textdomain("update-manager")
        except Exception, e:
          logging.warning("Error setting locales (%s)" % e)

        about=KAboutData("upgrade-tool","Upgrader","0.1","Dist Upgrade Tool for Kubuntu",KAboutData.License_GPL,"(c) 2007 Canonical Ltd",
        "http://wiki.kubuntu.org/KubuntuUpdateManager", "jriddell@ubuntu.com")
        about.addAuthor("Jonathan Riddell", None,"jriddell@ubuntu.com")
        KCmdLineArgs.init(["./dist-upgrade.py"],about)

        self.app = KApplication()

        self.mainWindow = KMainWindow()

        self.window_main = window_main(self.mainWindow)
        
        self.mainWindow.setCentralWidget(self.window_main)
        self.mainWindow.show()

        app = KApplication.kApplication()

        """FIXME set icon
        icons = gtk.icon_theme_get_default()
        """

        QTimer.singleShot(0, self.run)
        self.prev_step = 0 # keep a record of the latest step

        self._opCacheProgress = KDEOpProgress(self.window_main.progressbar_cache)
        self._fetchProgress = KDEFetchProgressAdapter(self)
        """
        self._cdromProgress = GtkCdromProgressAdapter(self)
        self._installProgress = GtkInstallProgressAdapter(self)
        # details dialog
        self.details_list = gtk.ListStore(gobject.TYPE_STRING)
        column = gtk.TreeViewColumn("")
        render = gtk.CellRendererText()
        column.pack_start(render, True)
        column.add_attribute(render, "markup", 0)
        self.treeview_details.append_column(column)
        self.treeview_details.set_model(self.details_list)
        self.vscrollbar_terminal.set_adjustment(self._term.get_adjustment())
        # work around bug in VteTerminal here
        self._term.realize()

        # reasonable fault handler
        sys.excepthook = self._handleException
        """

        self.app.exec_loop()

    def run(self):
        print "run()"
        app = DistUpgradeControler(self, {})
        app.run()

    def getFetchProgress(self):
        return self._fetchProgress

    def getOpCacheProgress(self):
        print "def getOpCacheProgress(self):"
        return self._opCacheProgress

    def error(self, pkg, errormsg):
        print "error: pkg: " + pkg + " errormsg: " + errormsg
        logging.error("got an error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
        #self.expander_terminal.set_expanded(True)
        ##self.parent.dialog_error.set_transient_for(self.parent.window_main)
        summary = _("Could not install '%s'") % pkg
        msg = _("The upgrade aborts now. Please report this bug against the 'update-manager' "
                "package and include the files in /var/log/dist-upgrade/ in the bugreport.")
        markup="<big><b>%s</b></big>\n\n%s" % (summary, msg)
        """
        self.parent.dialog_error.realize()
        self.parent.dialog_error.window.set_functions(gtk.gdk.FUNC_MOVE)
        self.parent.label_error.set_markup(markup)
        self.parent.textview_error.get_buffer().set_text(utf8(errormsg))
        self.parent.scroll_error.show()
        self.parent.dialog_error.run()
        self.parent.dialog_error.hide()
        """
        ##FIXME
        dialogue = dialog_error(self.window_main)
        dialogue.label_error.setText(markup)
        dialogue.textview_error.setText(utf8(errormsg))
        dialogue.run()

    def error(self, summary, msg, extended_msg=None):
        ##FIXME implement close and report bug buttons
        #self.expander_terminal.set_expanded(True)
        msg="<big><b>%s</b></big>\n\n%s" % (summary, msg)

        dialogue = dialog_error(self.window_main)
        dialogue.label_error.setText(msg)
        if extended_msg != None:
            dialogue.textview_error.setText(utf8(extended_msg))
            dialogue.textview_error.show()
        else:
            dialogue.textview_error.hide()
        dialogue.exec_loop()

        return False
