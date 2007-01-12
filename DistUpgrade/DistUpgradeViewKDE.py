from qt import *
from kdeui import *
from kdecore import *
from kparts import konsolePart

import sys
import logging
import time
import subprocess

import apt
import apt_pkg
import os

import pty

from apt.progress import InstallProgress
from DistUpgradeControler import DistUpgradeControler
from DistUpgradeView import DistUpgradeView, FuzzyTimeToStr, estimatedDownloadTime
from window_main import window_main
from dialog_error import dialog_error
from dialog_changes import dialog_changes

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
            self.parent.window_main.progress_text.setText("<i>" + _("About %s remaining") % FuzzyTimeToStr(self.eta) + "</i>")
        else:
            self.status.setText(_("Fetching file %li of %li") % (currentItem, self.totalItems))
            self.parent.window_main.progress_text.setText("  ")

        KApplication.kApplication().processEvents()
        return True

class KDEInstallProgressAdapter(InstallProgress):
    # timeout with no status change when the terminal is expanded
    # automatically
    TIMEOUT_TERMINAL_ACTIVITY = 240

    def __init__(self,parent):
        InstallProgress.__init__(self)
        self._cache = None
        self.label_status = parent.window_main.label_status
        self.progress = parent.window_main.progressbar_cache
        self.progress_text = parent.window_main.progress_text
        ##self.expander = parent.expander_terminal
        ##self.term = parent._term
        self.parent = parent
        # setup the child waiting
        ##reaper = vte.reaper_get()
        ##reaper.connect("child-exited", self.child_exited)
        # some options for dpkg to make it die less easily
        apt_pkg.Config.Set("DPkg::Options::","--force-overwrite")
        apt_pkg.Config.Set("DPkg::StopOnError","False")

    def startUpdate(self):
        self.finished = False
        # FIXME: add support for the timeout
        # of the terminal (to display something useful then)
        # -> longer term, move this code into python-apt 
        self.label_status.setText(_("Applying changes"))
        self.progress.setProgress(0)
        self.progress_text.setText(" ")
        ##self.expander.set_sensitive(True)
        ##self.term.show()
        # if no libgnome2-perl is installed show the terminal
        frontend="kde"
        """
        if self._cache:
          if not self._cache.has_key("libgnome2-perl") or \
             not self._cache["libgnome2-perl"].isInstalled:
            frontend = "dialog"
            self.expander.set_expanded(True)
        """
        self.env = ["VTE_PTY_KEEP_FD=%s"% self.writefd,
                    "DEBIAN_FRONTEND=%s" % frontend,
                    "APT_LISTCHANGES_FRONTEND=none"]
        # do a bit of time-keeping
        self.start_time = 0.0
        self.time_ui = 0.0
        self.last_activity = 0.0
        
    def error(self, pkg, errormsg):
        print "FIXME error()"
        logging.error("got an error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
        #self.expander_terminal.set_expanded(True)
        ##self.parent.dialog_error.set_transient_for(self.parent.window_main)
        summary = _("Could not install '%s'") % pkg
        msg = _("The upgrade aborts now. Please report this bug against the 'update-manager' "
                "package and include the files in /var/log/dist-upgrade/ in the bugreport.")
        markup="<big><b>%s</b></big>\n\n%s" % (summary, msg)
        self.parent.dialog_error.realize()
        self.parent.dialog_error.window.set_functions(gtk.gdk.FUNC_MOVE)
        self.parent.label_error.set_markup(markup)
        self.parent.textview_error.get_buffer().set_text(utf8(errormsg))
        self.parent.scroll_error.show()
        self.parent.dialog_error.run()
        self.parent.dialog_error.hide()

    def conffile(self, current, new):
        ##FIXME
        print "conffile(self, current, new):"
        logging.debug("got a conffile-prompt from dpkg for file: '%s'" % current)
        start = time.time()
        #self.expander.set_expanded(True)
        prim = _("Replace the customized configuration file\n'%s'?") % current
        sec = _("You will lose any changes you have made to this "
                "configuration file if you choose to replace it with "
                "a newer version.")
        markup = "<span weight=\"bold\" size=\"larger\">%s </span> \n\n%s" % (prim, sec)
        self.parent.label_conffile.set_markup(markup)
        self.parent.dialog_conffile.set_transient_for(self.parent.window_main)

        # now get the diff
        if os.path.exists("/usr/bin/diff"):
          cmd = ["/usr/bin/diff", "-u", current, new]
          diff = utf8(subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0])
          self.parent.textview_conffile.get_buffer().set_text(diff)
        else:
          self.parent.textview_conffile.get_buffer().set_text(_("The 'diff' command was not found"))
        res = self.parent.dialog_conffile.run()
        self.parent.dialog_conffile.hide()
        self.time_ui += time.time() - start
        # if replace, send this to the terminal
        if res == gtk.RESPONSE_YES:
          self.term.feed_child("y\n")
        else:
          self.term.feed_child("n\n")
        
    def fork(self):
        print "fork(self):"
        ##FIXME!!pid = self.term.forkpty(envv=self.env)
        #pid = 1
        #if pid == 0:
        #  # HACK to work around bug in python/vte and unregister the logging
        #  #      atexit func in the child
        #  sys.exitfunc = lambda: True
        #return pid
        (self.pid, self.master_fd) = pty.fork()
        if self.pid == 0:
            # stdin is /dev/null to prevent retarded maintainer scripts from
            # hanging with stupid questions
            #fd = os.open("/dev/null", os.O_RDONLY)
            #os.dup2(fd, 0)
            # *sigh* we can't do this because dpkg explodes when it can't
            # present its stupid conffile prompt
            pass
        logging.debug("pid is: %s" % self.pid)
        return self.pid

    def statusChange(self, pkg, percent, status):
        print "statusChange(self, pkg, percent, status):"
        # start the timer when the first package changes its status
        if self.start_time == 0.0:
          #print "setting start time to %s" % self.start_time
          self.start_time = time.time()
        self.progress.setProgress(self.percent)
        self.label_status.setText(status.strip())
        # start showing when we gathered some data
        if percent > 1.0:
          self.last_activity = time.time()
          self.activity_timeout_reported = False
          delta = self.last_activity - self.start_time
          # time wasted in conffile questions (or other ui activity)
          delta -= self.time_ui
          time_per_percent = (float(delta)/percent)
          eta = (100.0 - self.percent) * time_per_percent
          # only show if we have some sensible data (60sec < eta < 2days)
          if eta > 61.0 and eta < (60*60*24*2):
            self.progress_label.setText(_("About %s remaining") % FuzzyTimeToStr(eta))
          else:
            self.progress_label.setText(" ")

    def child_exited(self, term, pid, status):
        print "child_exited(self, term, pid, status):"
        self.apt_status = os.WEXITSTATUS(status)
        self.finished = True

    def waitChild(self):
        print "waitChild(self):"
        while not self.finished:
            self.updateInterface()
        return self.apt_status

    def finishUpdate(self):
        print "finishUpdate(self):"
        self.label_status.setText("")
    
    def updateInterface(self):
        print "updateInterface(self):"
        try:
          print "trying"
          InstallProgress.updateInterface(self)
          print "successful"
        except ValueError, e:
          logging.error("got ValueError from InstallPrgoress.updateInterface. Line was '%s' (%s)" % (self.read, e))
          # reset self.read so that it can continue reading and does not loop
	  self.read = ""
        # check if we haven't started yet with packages, pulse then
        if self.start_time == 0.0:
          ##FIXME self.progress.pulse()  makes it move back and forth
          time.sleep(0.2)
        # check about terminal activity
        if self.last_activity > 0 and \
           (self.last_activity + self.TIMEOUT_TERMINAL_ACTIVITY) < time.time():
          if not self.activity_timeout_reported:
            logging.warning("no activity on terminal for %s seconds (%s)" % (self.TIMEOUT_TERMINAL_ACTIVITY, self.label_status.get_text()))
            self.activity_timeout_reported = True
          ##FIXME self.parent.expander_terminal.set_expanded(True)
        KApplication.kApplication().processEvents()
        time.sleep(0.02)

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
        """
        self._installProgress = KDEInstallProgressAdapter(self)
        """
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

        self.box = QHBoxLayout(self.window_main.konsole_frame)
        self.konsole = konsolePart(self.window_main.konsole_frame, "konsole", self.window_main.konsole_frame, "konsole")
        self.konsole.setAutoStartShell(False)
        self.konsoleWidget = self.konsole.widget()
        #self.part = konsoleFactory.createReadOnlyPart("libkonsolepart", self.window_main.konsole_frame)
        #self.w = self.part.widget()
        self.box.addWidget(self.konsoleWidget)
        #self.w.setGeometry(30, 55, 500, 400)
        self.konsoleWidget.show()
        self.app.exec_loop()

    def run(self):
        print "run()"
        app = DistUpgradeControler(self, {})
        app.run()

    def getFetchProgress(self):
        return self._fetchProgress

    def getInstallProgress(self, cache):
        self._installProgress._cache = cache
        return self._installProgress

    def getOpCacheProgress(self):
        print "def getOpCacheProgress(self):"
        return self._opCacheProgress

    def updateStatus(self, msg):
        self.window_main.label_status.setText("%s" % msg)

    def setStep(self, step):
        ##FIXME if self.icontheme.rescan_if_needed():
        ##  logging.debug("icon theme changed, re-reading")
        # first update the "previous" step as completed
        ##size = gtk.ICON_SIZE_MENU
        ##attrlist=pango.AttrList()
        if self.prev_step:
            image = getattr(self.window_main,"image_step%i" % self.prev_step)
            label = getattr(self.window_main,"label_step%i" % self.prev_step)
            ##arrow = getattr(self.window_main,"arrow_step%i" % self.prev_step)
            ##label.set_property("attributes",attrlist)
            ##image.set_from_stock(gtk.STOCK_APPLY, size)
            image.setPixmap(QPixmap("/usr/share/apps/knetworkconf/pixmaps/kubuntu.png")) ##FIXME
            image.show()
            ##arrow.hide()
        self.prev_step = step
        # show the an arrow for the current step and make the label bold
        image = getattr(self.window_main,"image_step%i" % step)
        label = getattr(self.window_main,"label_step%i" % step)
        ##arrow = getattr(self.window_main,"arrow_step%i" % step)
        ##arrow.show()
        image.hide()
        label.setText("<b>" + label.text() + "</b>")

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

    def confirmChanges(self, summary, changes, downloadSize, actions=None):
        # FIXME: add a whitelist here for packages that we expect to be
        # removed (how to calc this automatically?)
        DistUpgradeView.confirmChanges(self, summary, changes, downloadSize)
        pkgs_remove = len(self.toRemove)
        pkgs_inst = len(self.toInstall)
        pkgs_upgrade = len(self.toUpgrade)
        msg = ""

        if pkgs_remove > 0:
            # FIXME: make those two seperate lines to make it clear
            #        that the "%" applies to the result of ngettext
            msg += gettext.ngettext("%d package is going to be removed.",
                                    "%d packages are going to be removed.",
                                    pkgs_remove) % pkgs_remove
            msg += " "
        if pkgs_inst > 0:
            msg += gettext.ngettext("%d new package is going to be "
                                    "installed.",
                                    "%d new packages are going to be "
                                    "installed.",pkgs_inst) % pkgs_inst
            msg += " "
        if pkgs_upgrade > 0:
            msg += gettext.ngettext("%d package is going to be upgraded.",
                                    "%d packages are going to be upgraded.",
                                    pkgs_upgrade) % pkgs_upgrade
            msg +=" "
        if downloadSize > 0:
            msg += _("\n\nYou have to download a total of %s. ") %\
                     apt_pkg.SizeToStr(downloadSize)
            msg += estimatedDownloadTime(downloadSize)
            msg += "."

        if (pkgs_upgrade + pkgs_inst + pkgs_remove) > 100:
            msg += "\n\n%s" % _("Fetching and installing the upgrade can take several hours and "\
                                "cannot be canceled at any time later.")

        msg += "\n\n<b>%s</b>" % _("To prevent data loss close all open "\
                                   "applications and documents.")

        # Show an error if no actions are planned
        if (pkgs_upgrade + pkgs_inst + pkgs_remove) < 1:
            # FIXME: this should go into DistUpgradeController
            summary = _("Your system is up-to-date")
            msg = _("There are no upgrades available for your system. "
                    "The upgrade will now be canceled.")
            self.error(summary, msg)
            return False

        ##FIXMEif actions != None:
        #    self.button_cancel_changes.set_use_stock(False)
        #    self.button_cancel_changes.set_use_underline(True)
        #    self.button_cancel_changes.set_label(actions[0])
        #    self.button_confirm_changes.set_label(actions[1])

        changesDialogue = dialog_changes(self.window_main)

        changesDialogue.label_summary.setText("<big><b>%s</b></big>" % summary)
        changesDialogue.label_changes.setText(msg)  ##FIXME s/\n/<br>/
        print "changes: " + msg
        print "summary: " + summary
        # fill in the details
        ##FIXME
        changesDialogue.treeview_details.clear()
        for rm in self.toRemove:
            changesDialogue.treeview_details.insertItem( QListViewItem(changesDialogue.treeview_details, _("<b>Remove %s</b>") % rm) )
        for inst in self.toInstall:
            changesDialogue.treeview_details.insertItem( QListViewItem(changesDialogue.treeview_details, _("Install %s") % inst) )
        for up in self.toUpgrade:
            changesDialogue.treeview_details.insertItem( QListViewItem(changesDialogue.treeview_details, _("Upgrade %s") % up) )
        #self.treeview_details.scroll_to_cell((0,))
        #self.dialog_changes.set_transient_for(self.window_main)
        #self.dialog_changes.realize()
        #self.dialog_changes.window.set_functions(gtk.gdk.FUNC_MOVE)
        #res = self.dialog_changes.run()
        res = changesDialogue.exec_loop()
        #self.dialog_changes.hide()
        if res == QDialog.Accepted:
            return True
        return False
