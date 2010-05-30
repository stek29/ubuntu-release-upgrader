# (c) 2005-2009 Canonical, GPL
#

from aptdaemon import client, errors
from aptdaemon.defer import inline_callbacks
from aptdaemon.gtkwidgets import AptProgressDialog

from InstallBackend import InstallBackend


class InstallBackendAptdaemon(InstallBackend):

    """Makes use of aptdaemon to refresh the cache and to install updates."""

    def __init__(self, window_main):
        InstallBackend.__init__(self, window_main)
        self.client = client.AptClient()

    @inline_callbacks
    def update(self):
        """Refresh the package list"""
        try:
            trans = yield self.client.update_cache(defer=True)
            self._run_in_dialog(trans, self.UPDATE)
        except errors.NotAuthorizedError:
            self.emit("action-done", self.UPDATE)
        except:
            self.emit("action-done", self.UPDATE)
            raise

    @inline_callbacks
    def commit(self, pkgs_install, pkgs_upgrade, close_on_done):
        """Commit a list of package adds and removes"""
        try:
            trans = yield self.client.commit_packages(pkgs_install, [], [],
                                                      [], pkgs_upgrade,
                                                      defer=True)
            self._run_in_dialog(trans, self.INSTALL)
        except errors.NotAuthorizedError:
            self.emit("action-done", self.INSTALL)
        except:
            self.emit("action-done", self.INSTALL)
            raise

    def _run_in_dialog(self, trans, action):
        dia = AptProgressDialog(trans, parent=self.window_main)
        dia.set_icon_name("update-manager")
        dia.connect("finished", self._on_finished, action)
        dia.run()

    def _on_finished(self, dialog, action):
        dialog.hide()
        self.emit("action-done", action)
