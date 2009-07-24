# (c) 2005-2009 Canonical, GPL
#

import gobject
import gtk

from aptdaemon import policykit
from aptdaemon import client
from aptdaemon.enums import *
from aptdaemon.gtkwidgets import (AptErrorDialog, 
                                  AptProgressDialog, 
                                  AptMessageDialog)

from InstallBackend import InstallBackend


class InstallBackendAptdaemon(InstallBackend):
    """The abstract backend that can install/remove packages"""

    def commit(self, cache):
        """Commit a list of package adds and removes"""
        self.ac = client.AptClient()
        add = []
        upgrade = []
        for pkg in cache:
                if pkg.markedInstall: 
                    add.append(pkg.name)
                elif pkg.markedUpgrade:
                    upgrade.append(pkg.name)
        if add:
            policykit.obtain_authorization(policykit.PK_ACTION_INSTALL_PACKAGES,
                                           self.window_main.window.xid)
        # parameter order: install, reinstall, remove, purge, upgrade
        t = self.ac.commit_packages(add, [], [], [], upgrade,
                                    exit_handler=self._on_exit)
        dia = AptProgressDialog(t, parent=self.window_main)
        dia.run()
        dia.hide()
        self._show_messages(t)

    def update(self):
        """Run a update to refresh the package list"""
        self.ac = client.AptClient()
        policykit.obtain_authorization(policykit.PK_ACTION_UPDATE_CACHE,
                                       self.window_main.window.xid)
        t = self.ac.update_cache(exit_handler=self._on_exit)
        dia = AptProgressDialog(t, parent=self.window_main, terminal=False)
        dia.run()
        dia.hide()
        self._show_messages(t)

    def _on_exit(self, trans, exit):
        if exit == EXIT_FAILED:
            d = AptErrorDialog(trans.get_error(), parent=self.window_main)
            d.run()
            d.hide()

    def _show_messages(self, trans):
        while gtk.events_pending():
            gtk.main_iteration()
        for msg in trans._messages:
            d = AptMessageDialog(msg.enum, msg.details, parent=self.window_main)
            d.run()
            d.hide()
