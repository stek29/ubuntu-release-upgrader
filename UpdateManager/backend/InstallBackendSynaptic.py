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

from InstallBackend import InstallBackend

class InstallBackendSynaptic(InstallBackend):
    """ Install backend based on synaptic """
    
    # synaptic actions
    (INSTALL, UPDATE) = range(2)

    def _run_synaptic(self, id, lock, cache=None, action=INSTALL):
        try:
            apt_pkg.PkgSystemUnLock()
        except SystemError:
            pass
        cmd = ["/usr/bin/gksu", 
               "--desktop", "/usr/share/applications/update-manager.desktop", 
               "--", "/usr/sbin/synaptic", "--hide-main-window",  
               "--non-interactive", "--parent-window-id", "%s" % (id) ]
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
            f = tempfile.NamedTemporaryFile()
            for pkg in cache:
                if pkg.markedInstall or pkg.markedUpgrade:
                    f.write("%s\tinstall\n" % pkg.name)
            cmd.append("--set-selections-file")
            cmd.append("%s" % f.name)
            f.flush()
            self.return_code = subprocess.call(cmd)
            f.close()
        elif action == self.UPDATE:
            cmd.append("--update-at-startup")
            self.return_code = subprocess.call(cmd)
        else:
            print "run_synaptic() called with unknown action"
            return False
        lock.release()

    def _perform_action(self, action, cache=None):
        lock = thread.allocate_lock()
        lock.acquire()
        t = thread.start_new_thread(self._run_synaptic,
                                    (self.window_main.window.xid,
                                     lock, cache, action))
        while lock.locked():
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.05)
        return self.return_code
        
    def update(self):
        return self._perform_action(self.UPDATE)

    def commit(self, cache):
        return self._perform_action(self.INSTALL, cache)



