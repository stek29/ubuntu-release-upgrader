# UpdateManager.py
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 2; coding: utf-8 -*-
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
from gi.repository import Gdk

import warnings
warnings.filterwarnings("ignore", "Accessed deprecated property", DeprecationWarning)

import sys
from gettext import gettext as _

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from .UnitySupport import UnitySupport
from .Dialogs import NoUpdatesDialog
from .Dialogs import NeedRestartDialog
from .InstallProgress import InstallProgress
from .UpdateProgress import UpdateProgress
from .UpdatesAvailable import UpdatesAvailable
from .Core.AlertWatcher import AlertWatcher
from .Core.roam import NetworkManagerHelper

# file that signals if we need to reboot
REBOOT_REQUIRED_FILE = "/var/run/reboot-required"

class UpdateManager(Gtk.Window):
  """ This class is the main window and work flow controller.  Panes will add
      themselves to the main window and it will morph between them."""

  def __init__(self, datadir, options):
    Gtk.Window.__init__(self)

    # Public members
    self.datadir = datadir
    self.options = options
    self.unity = UnitySupport()
    self.controller = None

    # Basic GTK+ parameters
    self.set_title(_("Software Updater"))
    self.set_icon_name("system-software-update")
    self.set_resizable(False)
    self.set_position(Gtk.WindowPosition.CENTER)
    self.set_size_request(500,-1)

    # Signals
    self.connect("delete-event", self.close)

    self._setup_dbus()

    # deal with no-focus-on-map
    if self.options.no_focus_on_map:
        self.set_focus_on_map(False)
        self.iconify()
        self.stick()
        self.set_urgency_hint(True)
        self.unity.set_urgency(True)
        self.initial_focus_id = self.connect(
            "focus-in-event", self.on_initial_focus_in)

  def on_initial_focus_in(self, widget, event):
      """callback run on initial focus-in (if started unmapped)"""
      self.unstick()
      self.set_urgency_hint(False)
      self.unity.set_urgency(False)
      self.disconnect(self.initial_focus_id)
      return False

  def push(self, pane, controller):
    child = self.get_child()
    if child is not None:
      if self.controller and hasattr(self.controller, "save_state"):
        self.controller.save_state()
      child.destroy()

    if pane is None:
      self.controller = None
      return

    pane.reparent(self)
    self.controller = controller

    # Reset state
    self.set_resizable(False)
    self.set_sensitive(True)
    if self.get_window() is not None:
      self.get_window().set_cursor(None)
      self.get_window().set_functions(Gdk.WMFunction.ALL)

    if self.controller and hasattr(self.controller, "restore_state"):
      self.controller.restore_state()

    pane.show()
    self.show()

  def close(self, widget, data=None):
    if not self.get_sensitive():
      return True

    if self.controller and hasattr(self.controller, "close"):
      if self.controller.close(): # let controller handle it as they will
        return

    self.exit()

  def exit(self):
    """ exit the application, save the state """
    self.push(None, None)
    sys.exit(0)

  def start_update(self):
    if self.options.no_update:
      self.start_available()
      return
    self._start_pane(UpdateProgress)

  def start_available(self, allow_restart=False):
    # If restart is needed, show that.  Else show no-update-needed.  Else
    # actually show the available updates.
    if allow_restart and os.path.exists(REBOOT_REQUIRED_FILE):
        self._start_pane(NeedRestartDialog)
    elif False:
        self._start_pane(NoUpdatesDialog)
    else:
      self._start_pane(UpdatesAvailable)

  def start_install(self):
    self._start_pane(InstallProgress)

  def _start_pane(self, pane_class):
    self.set_sensitive(False)
    if self.get_window() is not None:
      self.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
    pane = pane_class(self)
    pane.main()

  def _setup_dbus(self):
    """ this sets up a dbus listener if none is installed alread """
    # check if there is another g-a-i already and if not setup one
    # listening on dbus
    try:
        bus = dbus.SessionBus()
    except:
        print("warning: could not initiate dbus")
        return
    try:
        proxy_obj = bus.get_object('org.freedesktop.UpdateManager', 
                                   '/org/freedesktop/UpdateManagerObject')
        iface = dbus.Interface(proxy_obj, 'org.freedesktop.UpdateManagerIFace')
        iface.bringToFront()
        #print("send bringToFront")
        sys.exit(0)
    except dbus.DBusException:
         #print("no listening object (%s) " % e)
         bus_name = dbus.service.BusName('org.freedesktop.UpdateManager',bus)
         self.dbusController = UpdateManagerDbusController(self, bus_name)


class UpdateManagerDbusController(dbus.service.Object):
    """ this is a helper to provide the UpdateManagerIFace """
    def __init__(self, parent, bus_name,
                 object_path='/org/freedesktop/UpdateManagerObject'):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.parent = parent
        self.alert_watcher = AlertWatcher ()
        self.alert_watcher.connect("network-alert", self._on_network_alert)
        self.connected = False

    @dbus.service.method('org.freedesktop.UpdateManagerIFace')
    def bringToFront(self):
        self.parent.present()
        return True

    @dbus.service.method('org.freedesktop.UpdateManagerIFace')
    def upgrade(self):
        try:
            self.parent.start_install()
            return True
        except:
            return False

    def _on_network_alert(self, watcher, state):
        if state in NetworkManagerHelper.NM_STATE_CONNECTED_LIST:
            self.connected = True
        else:
            self.connected = False
