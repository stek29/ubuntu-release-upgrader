# DistUpgradeView.py 
#  
#  Copyright (c) 2004,2005 Canonical
#  
#  Author: Michael Vogt <michael.vogt@ubuntu.com>
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

import apt
import logging
import time
import sys
from DistUpgradeView import DistUpgradeView
from DistUpgradeConfigParser import DistUpgradeConfig
import os
import pty
import apt_pkg

class NonInteractiveFetchProgress(apt.progress.FetchProgress):
    def updateStatus(self, uri, descr, shortDescr, status):
        #logging.debug("Fetch: updateStatus %s %s" % (uri, status))
        pass

class NonInteractiveInstallProgress(apt.progress.InstallProgress):
    def __init__(self):
        apt.progress.InstallProgress.__init__(self)
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        os.environ["APT_LISTCHANGES_FRONTEND"] = "none"
        self.config = DistUpgradeConfig(".")
        if self.config.get("NonInteractive","ForceOverwrite"):
            apt_pkg.Config.Set("DPkg::Options::","--force-overwrite")
        
    def error(self, pkg, errormsg):
        logging.error("got a error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
    def conffile(self, current, new):
        logging.debug("got a conffile-prompt from dpkg for file: '%s'" % current)
	try:
          # don't overwrite
	  os.write(self.master_fd,"n\n")
 	except Exception, e:
	  logging.error("error '%s' when trying to write to the conffile"%e)
    def updateInterface(self):
	apt.progress.InstallProgress.updateInterface(self)
        try:
            sys.stdout.write("%s" % os.read(self.master_fd, 256))
        except:
            pass
	time.sleep(0.001)
    def fork(self):
        logging.debug("doing a pty.fork()")
        (self.pid, self.master_fd) = pty.fork()
        logging.debug("pid is: %s" % self.pid)
        return self.pid
        

class DistUpgradeViewNonInteractive(DistUpgradeView):
    " non-interactive version of the upgrade view "
    def __init__(self):
        pass
    def getOpCacheProgress(self):
        " return a OpProgress() subclass for the given graphic"
        return apt.progress.OpProgress()
    def getFetchProgress(self):
        " return a fetch progress object "
        return NonInteractiveFetchProgress()
    def getInstallProgress(self, cache=None):
        " return a install progress object "
        return NonInteractiveInstallProgress()
    def updateStatus(self, msg):
        """ update the current status of the distUpgrade based
            on the current view
        """
        pass
    def setStep(self, step):
        """ we have 5 steps current for a upgrade:
        1. Analyzing the system
        2. Updating repository information
        3. Performing the upgrade
        4. Post upgrade stuff
        5. Complete
        """
        pass
    def confirmChanges(self, summary, changes, downloadSize, actions=None):
        DistUpgradeView.confirmChanges(self, summary, changes, downloadSize, actions)
	logging.debug("toinstall: '%s'" % self.toInstall)
        logging.debug("toupgrade: '%s'" % self.toUpgrade)
        logging.debug("toremove: '%s'" % self.toRemove)
        return True
    def askYesNoQuestion(self, summary, msg):
        " ask a Yes/No question and return True on 'Yes' "
        return True
    def confirmRestart(self):
        " generic ask about the restart, can be overriden "
	logging.debug("confirmRestart() called")
        return False
    def error(self, summary, msg, extended_msg=None):
        " display a error "
        logging.error("%s %s (%s)" % (summary, msg, extended_msg))
    def abort(self):
        logging.error("view.abort called")
