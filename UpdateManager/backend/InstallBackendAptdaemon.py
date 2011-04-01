#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2005-2009 Canonical, GPL

from aptdaemon import client, errors
from defer import inline_callbacks
from aptdaemon.gtkwidgets import AptProgressDialog
from aptdaemon.enums import EXIT_SUCCESS

from UpdateManager.backend import InstallBackend
import apt_pkg

class InstallBackendAptdaemon(InstallBackend):

    """Makes use of aptdaemon to refresh the cache and to install updates."""

    def __init__(self, window_main):
        InstallBackend.__init__(self, window_main)
        self.client = client.AptClient()

    @inline_callbacks
    def update(self):
        """Refresh the package list"""
        try:
            apt_pkg.pkgsystem_unlock()
        except SystemError:
            pass
        try:
            trans = yield self.client.update_cache(defer=True)
            yield self._run_in_dialog(trans, self.UPDATE)
        except errors.NotAuthorizedError:
            self.emit("action-done", self.UPDATE, False, False)
        except:
            self.emit("action-done", self.UPDATE, True, False)
            raise

    @inline_callbacks
    def commit(self, pkgs_install, pkgs_upgrade, close_on_done):
        """Commit a list of package adds and removes"""
        try:
            apt_pkg.pkgsystem_unlock()
        except SystemError:
            pass
        try:
            reinstall = remove = purge = downgrade = []
            trans = yield self.client.commit_packages(
                pkgs_install, reinstall, remove, purge, pkgs_upgrade, 
                downgrade, defer=True)
            self._run_in_dialog(trans, self.INSTALL)
        except errors.NotAuthorizedError as e:
            self.emit("action-done", self.INSTALL, False, False)
        except Exception as e:
            self.emit("action-done", self.INSTALL, True, False)
            raise

    def _run_in_dialog(self, trans, action):
        dia = AptProgressDialog(trans, parent=self.window_main)
        dia.set_icon_name("update-manager")
        dia.connect("finished", self._on_finished, action)
        dia.run()

    def _on_finished(self, dialog, action):
        dialog.hide()
        self.emit("action-done", action, 
                  True, dialog._transaction.exit == EXIT_SUCCESS)

if __name__ == "__main__":
    import apt

    b = InstallBackendAptdaemon(None)
    b.commit(["2vcard"], [], False)

    import gtk
    gtk.main()
