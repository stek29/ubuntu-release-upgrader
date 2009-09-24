# (c) 2005-2009 Canonical, GPL
#

import gobject
import gtk

import dbus
from aptdaemon import client
from aptdaemon.enums import *
from aptdaemon.gtkwidgets import (AptErrorDialog, 
                                  AptProgressDialog, 
                                  AptMessageDialog)

from InstallBackend import InstallBackend


class InstallBackendAptdaemon(InstallBackend):
    """The abstract backend that can install/remove packages"""

    def _get_icon(self):
        theme = gtk.icon_theme_get_default ()
        icon = theme.load_icon("update-manager", 16, 0)
        return icon

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
        # parameter order: install, reinstall, remove, purge, upgrade
        t = self.ac.commit_packages(add, [], [], [], upgrade,
                                    exit_handler=self._on_exit)
        dia = AptProgressDialog(t, parent=self.window_main)
        dia.set_icon(self._get_icon())
        try:
            dia.run()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                pass
            else:
                raise
        dia.hide()
        self._show_messages(t)

    def update(self):
        """Run a update to refresh the package list"""
        self.ac = client.AptClient()
        t = self.ac.update_cache(exit_handler=self._on_exit)
        dia = AptProgressDialog(t, parent=self.window_main, terminal=False)
        dia.set_icon(self._get_icon())
        try:
            dia.run()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                pass
            else:
                raise
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
