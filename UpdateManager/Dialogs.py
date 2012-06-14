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

from gettext import gettext as _
from gettext import ngettext

class Dialog(SimpleGtkbuilderApp):
  def __init__(self, window_main):
    self.window_main = window_main
    SimpleGtkbuilderApp.__init__(self, self.window_main.datadir+"gtkbuilder/Dialog.ui",
                                 "update-manager")

  def main(self):
    self.window_main.push(self.pane_dialog, self)

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
  def __init__(self, datadir):
    Dialog.__init__(self, datadir)
    self.set_header(_("The software on this computer is up to date."))
    self.add_settings_button()
    self.add_button(Gtk.STOCK_OK, self.close).grab_focus()

  def close(self):
    sys.exit(0)


class ErrorDialog(Dialog):
  def __init__(self, datadir, header, desc=None):
    Dialog.__init__(self, datadir)
    self.set_header(header)
    if desc:
      self.set_desc(desc)
      self.label_desc.set_selectable(True)
    self.add_settings_button()
    self.add_button(Gtk.STOCK_OK, self.close).grab_focus()

  def close(self):
    sys.exit(0)


class NeedRestartDialog(Dialog):
  def __init__(self, datadir):
    Dialog.__init__(self, datadir)
    self.set_header(_("The computer needs to restart to finish installing updates."))
    self.add_button(_("_Restart"), self.restart)

  def close(self):
    sys.exit(0)

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

