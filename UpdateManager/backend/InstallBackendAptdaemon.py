# (c) 2005-2009 Canonical, GPL
#

from aptdaemon import client, enums
from aptdaemon.gtkwidgets import AptProgressDialog

from InstallBackend import InstallBackend

POLKIT_ERROR_NOT_AUTHORIZED = "org.freedesktop.PolicyKit.Error.NotAuthorized"

class InstallBackendAptdaemon(InstallBackend):

    """Makes use of aptdaemon to refresh the cache and to install updates."""

    def update(self):
        """Run a update to refresh the package list"""
        ac = client.AptClient()
        ac.update_cache(reply_handler=self._run_transaction,
                        error_handler=self._on_error)

    def commit(self, pkgs_install, pkgs_upgrade, close_on_done):
        """Commit a list of package adds and removes"""
        ac = client.AptClient()
        # parameter order: install, reinstall, remove, purge, upgrade
        _reply_handler = lambda trans: self._run_transaction(trans,
                                                             close_on_done)
        ac.commit_packages(pkgs_install, [], [], [], pkgs_upgrade,
                           reply_handler=_reply_handler,
                           error_handler=self._on_error)

    def _run_transaction(self, trans, close=True):
        dia = AptProgressDialog(trans, parent=self.window_main)
        dia.set_icon_name("update-manager")
        dia.connect("finished", self._on_finished)
        dia.run(show_error=True, close_on_finished=close,
                reply_handler=lambda: True,
                error_handler=self._on_error)

    def _on_finished(self, dialog):
        dialog.destroy()
        if dialog._transaction.role == enums.ROLE_UPDATE_CACHE:
            action = self.UPDATE
        else:
            action = self.INSTALL
        self.emit("action-done", action)

    def _on_error(self, error):
        if error.get_dbus_name() == POLKIT_ERROR_NOT_AUTHORIZED:
            # Should already be handled by the polkit agent
            pass
        else:
            #FIXME: Show an error dialog
            raise error
