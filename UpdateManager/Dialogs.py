# Dialogs.py
# -*- coding: utf-8 -*-
#  
#  Copyright (c) 2012 Canonical
#  
#  Author: Michael Terry <michael.terry@canonical.com>
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

from __future__ import absolute_import, print_function

from gi.repository import Gtk
from gi.repository import GObject
GObject.threads_init()

import warnings
warnings.filterwarnings("ignore", "Accessed deprecated property", DeprecationWarning)

import dbus
import os
import subprocess
import sys
import time
from .SimpleGtk3builderApp import SimpleGtkbuilderApp
from .DistUpgradeFetcher import DistUpgradeFetcherGtk
from .GtkProgress import GtkAcquireProgress

from gettext import gettext as _

class Dialog(SimpleGtkbuilderApp):
  def __init__(self, window_main):
    self.window_main = window_main
    self.focus_button = None
    SimpleGtkbuilderApp.__init__(self, self.window_main.datadir+"/gtkbuilder/Dialog.ui",
                                 "update-manager")

  def main(self):
    self.window_main.push(self.pane_dialog, self)
    if self.focus_button:
      self.focus_button.grab_focus()

  def run(self, parent=None):
    if self.focus_button:
      self.focus_button.grab_focus()
    if parent:
      self.window_dialog.set_transient_for(parent)
      self.window_dialog.set_modal(True)
    self.window_dialog.run()

  def close(self):
    sys.exit(0) # By default, exit the app

  def add_button(self, label, callback, secondary=False):
    # from_stock tries stock first and falls back to mnemonic
    button = Gtk.Button.new_from_stock(label)
    button.connect("clicked", lambda x: callback())
    button.show()
    self.buttonbox.add(button)
    self.buttonbox.set_child_secondary(button, secondary)
    return button

  def add_settings_button(self):
    if os.path.exists("/usr/bin/software-properties-gtk"):
      return self.add_button(_("Settings…"), self.on_settings_button_clicked, secondary=True)
    else:
      return None

  def on_settings_button_clicked(self):
    cmd = ["/usr/bin/software-properties-gtk",
           "--open-tab","2",
           # FIXME: once get_xid() is available via introspections, add 
           #        this back
           #"--toplevel", "%s" % self.window_main.get_window().get_xid() 
          ]
    self.window_main.set_sensitive(False)
    p = subprocess.Popen(cmd)
    while p.poll() is None:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.05)
    self.window_main.set_sensitive(True)

  def set_header(self, label):
    self.label_header.set_label(label)

  def set_desc(self, label):
    self.label_desc.set_label(label)
    self.label_desc.set_visible(bool(label))


class NoUpdatesDialog(Dialog):
  def __init__(self, window_main):
    Dialog.__init__(self, window_main)
    self.set_header(_("The software on this computer is up to date."))
    self.add_settings_button()
    self.focus_button = self.add_button(Gtk.STOCK_OK, self.close)


class DistUpgradeDialog(Dialog):
  def __init__(self, window_main, meta_release):
    Dialog.__init__(self, window_main)
    self.meta_release = meta_release
    self.set_header(_("The software on this computer is up to date."))
    # Translators: these are Ubuntu version names like "Ubuntu 12.04"
    self.set_desc(_("However, %s %s is now available (you have %s).") % (
                  meta_release.flavor_name,
                  meta_release.upgradable_to.version,
                  meta_release.current_dist_version))
    self.add_settings_button()
    self.add_button(_("Upgrade…"), self.upgrade)
    self.focus_button = self.add_button(Gtk.STOCK_OK, self.close)

  def upgrade(self):
    progress = GtkAcquireProgress(self.window_main, self.window_main.datadir,
                                  _("Downloading the release upgrade tool"))
    fetcher = DistUpgradeFetcherGtk(new_dist=self.meta_release.upgradable_to,
                                    parent=self.window_main,
                                    progress=progress,
                                    datadir=self.window_main.datadir)
    if self.window_main.options.sandbox:
      fetcher.run_options.append("--sandbox")
    fetcher.run()


class UnsupportedDialog(DistUpgradeDialog):
  def __init__(self, window_main, meta_release):
    DistUpgradeDialog.__init__(self, window_main, meta_release)
    # Translators: this is an Ubuntu version name like "Ubuntu 12.04"
    self.set_header(_("Software updates are no longer provided for %s %s.") % (
                    meta_release.flavor_name,
                    meta_release.current_dist_version))
    # Translators: this is an Ubuntu version name like "Ubuntu 12.04"
    self.set_desc(_("To stay secure, you should upgrade to %s %s.") % (
                  meta_release.flavor_name,
                  meta_release.upgradable_to.version))
    print("Hello!")

  def run(self, parent):
    # This field is used in tests/test_end_of_life.py
    print("Hello2!", self.window_main)
    self.window_main.no_longer_supported_nag = self.window_dialog
    DistUpgradeDialog.run(self, parent)


class PartialUpgradeDialog(Dialog):
  def __init__(self, window_main):
    Dialog.__init__(self, window_main)
    self.set_header(_("Not all updates can be installed"))
    self.set_desc(_("""Run a partial upgrade, to install as many updates as possible. 

This can be caused by:
 * A previous upgrade which didn't complete
 * Problems with some of the installed software
 * Unofficial software packages not provided by Ubuntu
 * Normal changes of a pre-release version of Ubuntu"""))
    self.add_settings_button()
    self.add_button(_("_Partial Upgrade"), self.upgrade)
    self.focus_button = self.add_button(_("_Continue"), Gtk.main_quit)

  def upgrade(self):
    os.execl("/usr/bin/gksu",
             "/usr/bin/gksu", "--desktop",
             "/usr/share/applications/update-manager.desktop",
             "--", "/usr/bin/update-manager", "--dist-upgrade")

  def main(self):
    Dialog.main(self)
    # Block progress until user has answered this question
    Gtk.main()


class ErrorDialog(Dialog):
  def __init__(self, window_main, header, desc=None):
    Dialog.__init__(self, window_main)
    self.set_header(header)
    if desc:
      self.set_desc(desc)
      self.label_desc.set_selectable(True)
    self.add_settings_button()
    self.focus_button = self.add_button(Gtk.STOCK_OK, self.close)

  def main(self):
    Dialog.main(self)
    # The label likes to start selecting everything (b/c it got focus before
    # we switched to our default button).
    self.label_desc.select_region(0, 0)
    # Since errors usually are outside the normal flow, we'll guarantee that
    # we don't continue with normal code flow by running our own loop here.
    # We won't screw anything up because the only thing this dialog will do
    # is exit.
    Gtk.main()


class NeedRestartDialog(Dialog):
  def __init__(self, window_main):
    Dialog.__init__(self, window_main)
    self.set_header(_("The computer needs to restart to finish installing updates."))
    self.focus_button = self.add_button(_("_Restart"), self.restart)

  def restart(self, *args, **kwargs):
    self._request_reboot_via_session_manager()

  def _request_reboot_via_session_manager(self):
    try:
        bus = dbus.SessionBus()
        proxy_obj = bus.get_object("org.gnome.SessionManager",
                                   "/org/gnome/SessionManager")
        iface = dbus.Interface(proxy_obj, "org.gnome.SessionManager")
        iface.RequestReboot()
    except dbus.DBusException:
        self._request_reboot_via_consolekit()
    except:
        pass

  def _request_reboot_via_consolekit(self):
    try:
        bus = dbus.SystemBus()
        proxy_obj = bus.get_object("org.freedesktop.ConsoleKit",
                                   "/org/freedesktop/ConsoleKit/Manager")
        iface = dbus.Interface(proxy_obj, "org.freedesktop.ConsoleKit.Manager")
        iface.Restart()
    except dbus.DBusException:
        pass

