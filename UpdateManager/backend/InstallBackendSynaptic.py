# (c) 2005-2007 Canonical, GPL
#

import apt_pkg
import subprocess
import gtk
import gtk.gdk
import thread
import time
import os
import tempfile
import gconf
from gettext import gettext as _

import gobject

from InstallBackend import InstallBackend

class InstallBackendSynaptic(InstallBackend):
    """ Install backend based on synaptic """
    
    # synaptic actions
    (INSTALL, UPDATE) = range(2)

    def _run_synaptic(self, action=INSTALL, cache=None):
        try:
            apt_pkg.PkgSystemUnLock()
        except SystemError:
            pass
        cmd = ["/usr/bin/gksu", 
               "--desktop", "/usr/share/applications/update-manager.desktop", 
               "--", "/usr/sbin/synaptic", "--hide-main-window",  
               "--non-interactive", "--parent-window-id",
               "%s" % self.window_main.window.xid ]
        if action == self.INSTALL:
            # close when update was successful (its ok to use a Synaptic::
            # option here, it will not get auto-saved, because synaptic does
            # not save options in non-interactive mode)
            gconfclient =  gconf.client_get_default()
            if gconfclient.get_bool("/apps/update-manager/autoclose_install_window"):
                cmd.append("-o")
                cmd.append("Synaptic::closeZvt=true")
            # custom progress strings
            cmd.append("--progress-str")
            cmd.append("%s" % _("Please wait, this can take some time."))
            cmd.append("--finish-str")
            cmd.append("%s" %  _("Update is complete"))
            tempf = tempfile.NamedTemporaryFile()
            for pkg in cache:
                if pkg.markedInstall or pkg.markedUpgrade:
                    tempf.write("%s\tinstall\n" % pkg.name)
            cmd.append("--set-selections-file")
            cmd.append("%s" % tempf.name)
            tempf.flush()
        elif action == self.UPDATE:
            cmd.append("--update-at-startup")
            tempf = None
        else:
            print "run_synaptic() called with unknown action"
            return False
        flags = gobject.SPAWN_DO_NOT_REAP_CHILD
        (pid, stdin, stdout, stderr) = gobject.spawn_async(cmd, flags=flags)
        gobject.child_watch_add(pid, self._on_synaptic_exit, (action, tempf))

    def _on_synaptic_exit(self, pid, condition, data):
        action, tempf = data
        if tempf:
            tempf.close()
        self.emit("action-done", action)

    def update(self):
        self._run_synaptic(self.UPDATE)

    def commit(self, cache):
        self._run_synaptic(self.INSTALL, cache)



