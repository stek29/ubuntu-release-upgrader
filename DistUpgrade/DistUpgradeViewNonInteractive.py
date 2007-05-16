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
from DistUpgradeView import DistUpgradeView, InstallProgress
from DistUpgradeConfigParser import DistUpgradeConfig
import os
import pty
import apt_pkg
import select
import fcntl
import string
import re

class NonInteractiveFetchProgress(apt.progress.FetchProgress):
    def updateStatus(self, uri, descr, shortDescr, status):
        #logging.debug("Fetch: updateStatus %s %s" % (uri, status))
        pass

class NonInteractiveInstallProgress(InstallProgress):
    def __init__(self):
        InstallProgress.__init__(self)
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        os.environ["APT_LISTCHANGES_FRONTEND"] = "none"
        self.config = DistUpgradeConfig(".")
        if self.config.getboolean("NonInteractive","ForceOverwrite"):
            apt_pkg.Config.Set("DPkg::Options::","--force-overwrite")
        # default to 1200 sec timeout
        self.timeout = 1200
        try:
            self.timeout = self.config.getint("NonInteractive","TerminalTimeout")
        except Exception, e:
            pass
        
    def error(self, pkg, errormsg):
        logging.error("got a error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
    def conffile(self, current, new):
        logging.warning("got a conffile-prompt from dpkg for file: '%s'" % current)
	try:
          # don't overwrite
	  os.write(self.master_fd,"n\n")
 	except Exception, e:
	  logging.error("error '%s' when trying to write to the conffile"%e)

    def startUpdate(self):
        self.last_activity = time.time()
          
    def updateInterface(self):
        if self.statusfd == None:
            return

        if (self.last_activity + self.timeout) < time.time():
            logging.warning("no activity %s seconds (%s) - sending ctrl-c" % (self.timeout, self.status))
            os.write(self.master_fd,chr(3))


        # read status fd from dpkg
        # from python-apt/apt/progress.py (but modified a bit)
        # -------------------------------------------------------------
        res = select.select([self.statusfd],[],[],0.1)
        while len(res[0]) > 0:
            self.last_activity = time.time()
            while not self.read.endswith("\n"):
                self.read += os.read(self.statusfd.fileno(),1)
            if self.read.endswith("\n"):
                s = self.read
                #print s
                (status, pkg, percent, status_str) = string.split(s, ":")
                if status == "pmerror":
                    self.error(pkg,status_str)
                elif status == "pmconffile":
                    # we get a string like this:
                    # 'current-conffile' 'new-conffile' useredited distedited
                    match = re.compile("\s*\'(.*)\'\s*\'(.*)\'.*").match(status_str)
                    if match:
                        self.conffile(match.group(1), match.group(2))
                elif status == "pmstatus":
                    if (float(percent) != self.percent or 
                        status_str != self.status):
                        self.statusChange(pkg, float(percent), status_str.strip())
                        self.percent = float(percent)
                        self.status = string.strip(status_str)
                        sys.stdout.write("[%s] %s: %s\n" % (float(percent), pkg, status_str.strip()))
                        sys.stdout.flush()
            self.read = ""
            res = select.select([self.statusfd],[],[],0.1)
        # -------------------------------------------------------------

        #fcntl.fcntl(self.master_fd, fcntl.F_SETFL, os.O_NDELAY)
        # read master fd (terminal output)
        res = select.select([self.master_fd],[],[],0.1)
        while len(res[0]) > 0:
           self.last_activity = time.time()
           try:
               s = os.read(self.master_fd, 1)
               sys.stdout.write("%s" % s)
           except OSError,e:
               # happens after we are finished because the fd is closed
               return
           res = select.select([self.master_fd],[],[],0.1)
        sys.stdout.flush()

    def fork(self):
        logging.debug("doing a pty.fork()")
        (self.pid, self.master_fd) = pty.fork()
        if self.pid != 0:
            logging.debug("pid is: %s" % self.pid)
        return self.pid
        

class DistUpgradeViewNonInteractive(DistUpgradeView):
    " non-interactive version of the upgrade view "
    def __init__(self):
        self.config = DistUpgradeConfig(".")
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
        # ignore if we don't have this option
        try:
            # rebooting here makes sense if we run e.g. in qemu
            return self.config.getboolean("NonInteractive","RealReboot")
        except Exception, e:
            logging.debug("no RealReboot found, returning false (%s) " % e)
            return False
    def error(self, summary, msg, extended_msg=None):
        " display a error "
        logging.error("%s %s (%s)" % (summary, msg, extended_msg))
    def abort(self):
        logging.error("view.abort called")


if __name__ == "__main__":

  view = DistUpgradeViewNonInteractive()
  fp = NonInteractiveFetchProgress()
  ip = NonInteractiveInstallProgress()

  cache = apt.Cache()
  for pkg in sys.argv[1:]:
    #if cache[pkg].isInstalled:
    #  cache[pkg].markDelete()
    #else:
    cache[pkg].markInstall()
  cache.commit(fp,ip)
  time.sleep(2)
  sys.exit(0)
