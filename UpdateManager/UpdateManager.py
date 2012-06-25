# UpdateManager.py
#  
#  Copyright (c) 2004-2012 Canonical
#                2004 Michiel Sikkes
#                2005 Martin Willemoes Hansen
#                2010 Mohamed Amine IL Idrissi
#  
#  Author: Michiel Sikkes <michiel@eyesopened.nl>
#          Michael Vogt <mvo@debian.org>
#          Martin Willemoes Hansen <mwh@sysrq.dk>
#          Mohamed Amine IL Idrissi <ilidrissiamine@gmail.com>
#          Alex Launi <alex.launi@canonical.com>
#          Michael Terry <michael.terry@canonical.com>
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
from gi.repository import GObject
from gi.repository import Gio
GObject.threads_init()
from gi.repository import Pango

import warnings
warnings.filterwarnings("ignore", "Accessed deprecated property", DeprecationWarning)

import apt_pkg

import sys
import os
import re
import logging
import operator
import subprocess
import time
import threading
import xml.sax.saxutils

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from .GtkProgress import GtkAcquireProgress, GtkOpProgressInline
from .backend import get_backend

from gettext import gettext as _
from gettext import ngettext


from .Core.utils import (humanize_size,
                         on_battery,
                         inhibit_sleep,
                         allow_sleep)
from .Core.UpdateList import UpdateList
from .Core.MyCache import MyCache
from .Core.AlertWatcher import AlertWatcher

from DistUpgrade.DistUpgradeCache import NotEnoughFreeSpaceError
from .DistUpgradeFetcher import DistUpgradeFetcherGtk

from .ChangelogViewer import ChangelogViewer
from .SimpleGtk3builderApp import SimpleGtkbuilderApp
from .MetaReleaseGObject import MetaRelease
from .UnitySupport import UnitySupport


#import pdb

# FIXME:
# - kill "all_changes" and move the changes into the "Update" class

# list constants
(LIST_CONTENTS, LIST_NAME, LIST_PKG, LIST_ORIGIN, LIST_TOGGLE_CHECKED) = range(5)

# file that signals if we need to reboot
REBOOT_REQUIRED_FILE = "/var/run/reboot-required"

# NetworkManager enums
from .Core.roam import NetworkManagerHelper

def show_dist_no_longer_supported_dialog(parent=None):
    """ show a no-longer-supported dialog """
    msg = "<big><b>%s</b></big>\n\n%s" % (
        _("Your Ubuntu release is not supported anymore."),
        _("You will not get any further security fixes or critical "
          "updates. "
          "Please upgrade to a later version of Ubuntu."))
    dialog = Gtk.MessageDialog(parent, 0, Gtk.MessageType.WARNING,
                               Gtk.ButtonsType.CLOSE,"")
    dialog.set_title("")
    dialog.set_markup(msg)
    button = Gtk.LinkButton(uri="http://www.ubuntu.com/releaseendoflife",
                            label=_("Upgrade information"))
    button.show()
    dialog.get_content_area().pack_end(button, True, True, 0)
    # this data used in the test to get the dialog
    if parent:
        parent.no_longer_supported_nag = dialog
    dialog.run()
    dialog.destroy()
    if parent:
        del parent.no_longer_supported_nag


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
        self.parent.window_main.present()
        return True

    @dbus.service.method('org.freedesktop.UpdateManagerIFace')
    def upgrade(self):
        try:
            self.parent.cache.checkFreeSpace()
            self.parent.invoke_manager()
            return True
        except:
            return False

    def _on_network_alert(self, watcher, state):
        if state in NetworkManagerHelper.NM_STATE_CONNECTED_LIST:
            self.connected = True
        else:
            self.connected = False

class UpdateManager(SimpleGtkbuilderApp):

  def __init__(self, datadir, options):
    self.setupDbus()
    self.datadir = datadir
    self.options = options
    SimpleGtkbuilderApp.__init__(self, datadir+"gtkbuilder/UpdateManager.ui",
                                 "update-manager")

    # Used for inhibiting power management
    self.sleep_cookie = None
    self.sleep_dev = None

    # workaround for LP: #945536
    self.clearing_store = False

    self.window_main.set_sensitive(False)
    self.window_main.grab_focus()
    self.button_close.grab_focus()
    self.dl_size = 0
    self.connected = True

    # create text view
    self.textview_changes = ChangelogViewer()
    self.textview_changes.show()
    self.scrolledwindow_changes.add(self.textview_changes)
    changes_buffer = self.textview_changes.get_buffer()
    changes_buffer.create_tag("versiontag", weight=Pango.Weight.BOLD)

    # expander
    self.expander_details.connect("activate", self.pre_activate_details)
    self.expander_details.connect("notify::expanded", self.activate_details)
    self.expander_desc.connect("notify::expanded", self.activate_desc)

    # useful exit stuff
    self.window_main.connect("delete_event", self.close)
    self.button_close.connect("clicked", lambda w: self.exit())

    # the treeview (move into it's own code!)
    self.store = Gtk.ListStore(str, str, GObject.TYPE_PYOBJECT, 
                               GObject.TYPE_PYOBJECT, bool)
    self.treeview_update.set_model(self.store)
    self.treeview_update.set_headers_clickable(True);
    self.treeview_update.set_direction(Gtk.TextDirection.LTR)

    tr = Gtk.CellRendererText()
    tr.set_property("xpad", 6)
    tr.set_property("ypad", 6)
    cr = Gtk.CellRendererToggle()
    cr.set_property("activatable", True)
    cr.set_property("xpad", 6)
    cr.connect("toggled", self.toggled)

    column_install = Gtk.TreeViewColumn(_("Install"), cr, active=LIST_TOGGLE_CHECKED)
    column_install.set_cell_data_func (cr, self.install_column_view_func)
    column = Gtk.TreeViewColumn(_("Name"), tr, markup=LIST_CONTENTS)
    column.set_resizable(True)

    column_install.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    column_install.set_fixed_width(30)
    column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
    column.set_fixed_width(100)
    self.treeview_update.set_fixed_height_mode(False)

    self.treeview_update.append_column(column_install)
    column_install.set_visible(True)
    self.treeview_update.append_column(column)
    self.treeview_update.set_search_column(LIST_NAME)
    self.treeview_update.connect("button-press-event", self.show_context_menu)

    # setup the help viewer and disable the help button if there
    # is no viewer available
    #self.help_viewer = HelpViewer("update-manager")
    #if self.help_viewer.check() == False:
    #    self.button_help.set_sensitive(False)

    if not os.path.exists("/usr/bin/software-properties-gtk"):
        self.button_settings.set_sensitive(False)

    self.settings =  Gio.Settings("com.ubuntu.update-manager")
    # init show version
    self.show_versions = self.settings.get_boolean("show-versions")
    # init summary_before_name
    self.summary_before_name = self.settings.get_boolean("summary-before-name")

    # get progress object
    self.progress = GtkOpProgressInline(
        self.progressbar_cache_inline, self.window_main)

    #set minimum size to prevent the headline label blocking the resize process
    self.window_main.set_size_request(500,-1) 
    # restore details state, which will trigger a resize if necessary
    self.expander_details.set_expanded(self.settings.get_boolean("show-details"))
    # deal with no-focus-on-map
    if options.no_focus_on_map:
        self.window_main.set_focus_on_map(False)
        if self.progress._window:
            self.progress._window.set_focus_on_map(False)
    # show the main window
    self.window_main.show()
    # get the install backend
    self.install_backend = get_backend(self.window_main)
    self.install_backend.connect("action-done", self._on_backend_done)

    # Create Unity launcher quicklist
    # FIXME: instead of passing parent we really should just send signals
    self.unity = UnitySupport(parent=self)

    # it can only the iconified *after* it is shown (even if the docs
    # claim otherwise)
    if options.no_focus_on_map:
        self.window_main.iconify()
        self.window_main.stick()
        self.window_main.set_urgency_hint(True)
        self.unity.set_urgency(True)
        self.initial_focus_id = self.window_main.connect(
            "focus-in-event", self.on_initial_focus_in)
    
    # Alert watcher
    self.alert_watcher = AlertWatcher()
    self.alert_watcher.connect("network-alert", self._on_network_alert)
    self.alert_watcher.connect("battery-alert", self._on_battery_alert)
    self.alert_watcher.connect("network-3g-alert", self._on_network_3g_alert)


  def install_all_updates (self, menu, menuitem, data):
    self.select_all_updgrades (None)
    self.on_button_install_clicked (None)

  def on_initial_focus_in(self, widget, event):
      """callback run on initial focus-in (if started unmapped)"""
      widget.unstick()
      widget.set_urgency_hint(False)
      self.unity.set_urgency(False)
      self.window_main.disconnect(self.initial_focus_id)
      return False

  def warn_on_battery(self):
      """check and warn if on battery"""
      if on_battery():
          self.dialog_on_battery.set_transient_for(self.window_main)
          self.dialog_on_battery.set_title("")
          res = self.dialog_on_battery.run()
          self.dialog_on_battery.hide()
          if res != Gtk.ResponseType.YES:
              sys.exit()

  def install_column_view_func(self, cell_layout, renderer, model, iter, data):
    pkg = model.get_value(iter, LIST_PKG)
    if pkg is None:
        renderer.set_property("activatable", True)
        return
    current_state = renderer.get_property("active")
    to_install = pkg.marked_install or pkg.marked_upgrade
    renderer.set_property("active", to_install)
    # we need to update the store as well to ensure orca knowns
    # about state changes (it will not read view_func changes)
    if to_install != current_state:
        self.store[iter][LIST_TOGGLE_CHECKED] = to_install
    if pkg.name in self.list.held_back:
        renderer.set_property("activatable", False)
    else: 
        renderer.set_property("activatable", True)

  def setupDbus(self):
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


  def close(self, widget, data=None):
    if self.window_main.get_property("sensitive") is False:
        return True
    else:
        self.exit()

  
  def set_changes_buffer(self, changes_buffer, text, name, srcpkg):
    changes_buffer.set_text("")
    lines = text.split("\n")
    if len(lines) == 1:
      changes_buffer.set_text(text)
      return
    
    for line in lines:
      end_iter = changes_buffer.get_end_iter()
      version_match = re.match(r'^%s \((.*)\)(.*)\;.*$' % re.escape(srcpkg), line)
      #bullet_match = re.match("^.*[\*-]", line)
      author_match = re.match("^.*--.*<.*@.*>.*$", line)
      if version_match:
        version = version_match.group(1)
        #upload_archive = version_match.group(2).strip()
        version_text = _("Version %s: \n") % version
        changes_buffer.insert_with_tags_by_name(end_iter, version_text, "versiontag")
      elif (author_match):
        pass
      else:
        changes_buffer.insert(end_iter, line+"\n")
        

  def on_treeview_update_cursor_changed(self, widget):
    path = widget.get_cursor()[0]
    # check if we have a path at all
    if path == None:
      return
    model = widget.get_model()
    iter = model.get_iter(path)

    # set descr
    pkg = model.get_value(iter, LIST_PKG)
    if (pkg is None or pkg.candidate is None or
        pkg.candidate.description is None):
      changes_buffer = self.textview_changes.get_buffer()
      changes_buffer.set_text("")
      desc_buffer = self.textview_descr.get_buffer()
      desc_buffer.set_text("")
      self.notebook_details.set_sensitive(False)
      return
    long_desc = pkg.candidate.description
    self.notebook_details.set_sensitive(True)
    # do some regular expression magic on the description
    # Add a newline before each bullet
    p = re.compile(r'^(\s|\t)*(\*|0|-)',re.MULTILINE)
    long_desc = p.sub('\n*', long_desc)
    # replace all newlines by spaces
    p = re.compile(r'\n', re.MULTILINE)
    long_desc = p.sub(" ", long_desc)
    # replace all multiple spaces by newlines
    p = re.compile(r'\s\s+', re.MULTILINE)
    long_desc = p.sub("\n", long_desc)

    desc_buffer = self.textview_descr.get_buffer()
    desc_buffer.set_text(long_desc)

    # now do the changelog
    name = model.get_value(iter, LIST_NAME)
    if name == None:
      return

    changes_buffer = self.textview_changes.get_buffer()
    
    # check if we have the changes already and if so, display them 
    # (even if currently disconnected)
    if name in self.cache.all_changes:
      changes = self.cache.all_changes[name]
      srcpkg = self.cache[name].candidate.source_name
      self.set_changes_buffer(changes_buffer, changes, name, srcpkg)
    # if not connected, do not even attempt to get the changes
    elif not self.connected:
        changes_buffer.set_text(
            _("No network connection detected, you can not download "
              "changelog information."))
    # else, get it from the entwork
    else:
      if self.expander_details.get_expanded():
        lock = threading.Lock()
        lock.acquire()
        changelog_thread = threading.Thread(
            target=self.cache.get_news_and_changelog, args=(name, lock))
        changelog_thread.start()
        changes_buffer.set_text("%s\n" % _("Downloading list of changes..."))
        iter = changes_buffer.get_iter_at_line(1)
        anchor = changes_buffer.create_child_anchor(iter)
        button = Gtk.Button(stock="gtk-cancel")
        self.textview_changes.add_child_at_anchor(button, anchor)
        button.show()
        id = button.connect("clicked",
                            lambda w,lock: lock.release(), lock)
        # wait for the dl-thread
        while lock.locked():
          time.sleep(0.01)
          while Gtk.events_pending():
            Gtk.main_iteration()
        # download finished (or canceld, or time-out)
        button.hide()
        if button.handler_is_connected(id):
            button.disconnect(id)
    # check if we still are in the right pkg (the download may have taken
    # some time and the user may have clicked on a new pkg)
    path  = widget.get_cursor()[0]
    if path == None:
      return
    now_name = widget.get_model()[path][LIST_NAME]
    if name != now_name:
        return
    # display NEWS.Debian first, then the changelog
    changes = ""
    srcpkg = self.cache[name].candidate.source_name
    if name in self.cache.all_news:
        changes += self.cache.all_news[name]
    if name in self.cache.all_changes:
        changes += self.cache.all_changes[name]
    if changes:
        self.set_changes_buffer(changes_buffer, changes, name, srcpkg)

  def show_context_menu(self, widget, event):
    """
    Show a context menu if a right click was performed on an update entry
    """
    if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
        # need to keep a reference here of menu, otherwise it gets
        # deleted when it goes out of scope and no menu is visible
        # (bug #806949)
        self.menu = menu = Gtk.Menu()
        item_select_none = Gtk.MenuItem.new_with_mnemonic(_("_Deselect All"))
        item_select_none.connect("activate", self.select_none_updgrades)
        menu.append(item_select_none)
        num_updates = self.cache.install_count
        if num_updates == 0:
            item_select_none.set_property("sensitive", False)
        item_select_all = Gtk.MenuItem.new_with_mnemonic(_("Select _All"))
        item_select_all.connect("activate", self.select_all_updgrades)
        menu.append(item_select_all)
        menu.show_all()
        menu.popup_for_device(
            None, None, None, None, None, event.button, event.time)
        menu.show()
        return True

  # we need this for select all/unselect all
  def _toggle_origin_headers(self, new_selection_value):
    """ small helper that will set/unset the origin headers
    """
    model = self.treeview_update.get_model()
    for row in model:
        if not model.get_value(row.iter, LIST_PKG):
            model.set_value(row.iter, LIST_TOGGLE_CHECKED, new_selection_value)

  def select_all_updgrades(self, widget):
    """
    Select all updates
    """
    self.setBusy(True)
    self.cache.saveDistUpgrade()
    self._toggle_origin_headers(True)
    self.treeview_update.queue_draw()
    self.refresh_updates_count()
    self.setBusy(False)

  def select_none_updgrades(self, widget):
    """
    Select none updates
    """
    self.setBusy(True)
    self.cache.clear()
    self._toggle_origin_headers(False)
    self.treeview_update.queue_draw()
    self.refresh_updates_count()
    self.setBusy(False)

  def setBusy(self, flag):
      """ Show a watch cursor if the app is busy for more than 0.3 sec.
      Furthermore provide a loop to handle user interface events """
      if self.window_main.get_window() is None:
          return
      if flag == True:
          self.window_main.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
      else:
          self.window_main.get_window().set_cursor(None)
      while Gtk.events_pending():
          Gtk.main_iteration()

  def refresh_updates_count(self):
      self.button_install.set_sensitive(self.cache.install_count)
      try:
          inst_count = self.cache.install_count
          self.dl_size = self.cache.required_download
          download_str = ""
          if self.dl_size != 0:
              download_str = _("%s will be downloaded.") % (humanize_size(self.dl_size))
              self.image_downsize.set_sensitive(True)
              # do not set the buttons to sensitive/insensitive until NM
              # can deal with dialup connections properly
              #if self.alert_watcher.network_state != NM_STATE_CONNECTED:
              #    self.button_install.set_sensitive(False)
              #else:
              #    self.button_install.set_sensitive(True)
              self.button_install.set_sensitive(True)
              self.unity.set_install_menuitem_visible(True)
          else:
              if inst_count > 0:
                  download_str = ngettext("The update has already been downloaded.",
                  "The updates have already been downloaded.", inst_count)
                  self.button_install.set_sensitive(True)
                  self.unity.set_install_menuitem_visible(True)
              else:
                  download_str = _("There are no updates to install.")
                  self.button_install.set_sensitive(False)
                  self.unity.set_install_menuitem_visible(False)
              self.image_downsize.set_sensitive(False)
          self.label_downsize.set_text(download_str)
          self.hbox_downsize.show()
          self.vbox_alerts.show()
      except SystemError as e:
          print("required_download could not be calculated: %s" % e)
          self.label_downsize.set_markup(_("Unknown download size."))
          self.image_downsize.set_sensitive(False)
          self.hbox_downsize.show()
          self.vbox_alerts.show()

  def update_count(self):
      """activate or disable widgets and show dialog texts correspoding to
         the number of available updates"""
      self.refresh_updates_count()
      num_updates = self.cache.install_count

      # setup unity stuff
      self.unity.set_updates_count(num_updates)

      if num_updates == 0:
          text_header= _("The software on this computer is up to date.")
          self.label_downsize.set_text("\n")
          if self.cache.keep_count() == 0:
              self.notebook_details.set_sensitive(False)
              self.treeview_update.set_sensitive(False)
          self.button_install.set_sensitive(False)
          self.unity.set_install_menuitem_visible(False)
          self.button_close.grab_default()
          self.textview_changes.get_buffer().set_text("")
          self.textview_descr.get_buffer().set_text("")
      else:
          # show different text on first run (UX team suggestion)
          firstrun = self.settings.get_boolean("first-run")
          if firstrun:
              text_header = _("Updated software has been issued since %s was released. Do you want to install it now?") % self.meta.current_dist_description
              self.settings.set_boolean("first-run", False)
          else:
              text_header = _("Updated software is available for this computer. Do you want to install it now?")
          self.notebook_details.set_sensitive(True)
          self.treeview_update.set_sensitive(True)
          self.button_install.grab_default()
          self.treeview_update.set_cursor(Gtk.TreePath.new_from_string("1"), None, False)
      self.label_header.set_markup(text_header)
      return True

  # Before we shrink the window, capture the size
  def pre_activate_details(self, expander):
    expanded = self.expander_details.get_expanded()
    if expanded:
      self.save_state()

  def activate_details(self, expander, data):
    expanded = self.expander_details.get_expanded()
    self.settings.set_boolean("show-details",expanded)
    if expanded:
      self.on_treeview_update_cursor_changed(self.treeview_update)
      self.restore_state()
    self.window_main.set_resizable(expanded)

  def activate_desc(self, expander, data):
    expanded = self.expander_desc.get_expanded()
    self.expander_desc.set_vexpand(expanded)

  #def on_button_help_clicked(self, widget):
  #  self.help_viewer.run()

  def on_button_settings_clicked(self, widget):
    #print("on_button_settings_clicked")
    try:
        apt_pkg.pkgsystem_unlock()
    except SystemError:
        pass
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
    self.fillstore()

  def on_button_install_clicked(self, widget):
    #print("on_button_install_clicked")
    err_sum = _("Not enough free disk space")
    err_long= _("The upgrade needs a total of %s free space on disk '%s'. "
                "Please free at least an additional %s of disk "
                "space on '%s'. "
                "Empty your trash and remove temporary "
                "packages of former installations using "
                "'sudo apt-get clean'.")
    # check free space and error if its not enough
    try:
        self.cache.checkFreeSpace()
    except NotEnoughFreeSpaceError as e:
        for req in e.free_space_required_list:
            self.error(err_sum, err_long % (req.size_total,
                                            req.dir,
                                            req.size_needed,
                                            req.dir))
        return
    except SystemError as e:
        logging.exception("free space check failed")
    self.invoke_manager()
    
  def on_button_restart_required_clicked(self, button=None):
      self._request_reboot_via_session_manager()

  def show_reboot_required_info(self):
    self.frame_restart_required.show()
    self.label_restart_required.set_text(_("The computer needs to restart to "
                                       "finish installing updates. Please "
                                       "save your work before continuing."))

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

  def invoke_manager(self):
    # check first if no other package manager is runing

    # don't display apt-listchanges, we already showed the changelog
    os.environ["APT_LISTCHANGES_FRONTEND"]="none"

    # Do not suspend during the update process
    (self.sleep_dev, self.sleep_cookie) = inhibit_sleep()

    # set window to insensitive
    self.window_main.set_sensitive(False)
    self.window_main.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))

    # If the progress dialog should be closed automatically afterwards
    settings = Gio.Settings("com.ubuntu.update-manager")
    close_on_done = settings.get_boolean("autoclose-install-window")
    # Get the packages which should be installed and update
    pkgs_install = []
    pkgs_upgrade = []
    for pkg in self.cache:
        if pkg.marked_install:
            pkgs_install.append(pkg.name)
        elif pkg.marked_upgrade:
            pkgs_upgrade.append(pkg.name)
    self.install_backend.commit(pkgs_install, pkgs_upgrade, close_on_done)

  def _on_backend_done(self, backend, action, authorized, success):
    # check if there is a new reboot required notification
    if os.path.exists(REBOOT_REQUIRED_FILE):
        self.show_reboot_required_info()
    if authorized:
        msg = _("Reading package information")
        self.label_cache_progress_title.set_label("<b><big>%s</big></b>" % msg)
        self.fillstore()

    # Allow suspend after synaptic is finished
    if self.sleep_cookie:
        allow_sleep(self.sleep_dev, self.sleep_cookie)
        self.sleep_cookie = self.sleep_dev = None
    self.window_main.set_sensitive(True)
    self.window_main.get_window().set_cursor(None)

  def _on_network_alert(self, watcher, state):
      # do not set the buttons to sensitive/insensitive until NM
      # can deal with dialup connections properly
      if state in NetworkManagerHelper.NM_STATE_CONNECTING_LIST:
          self.label_offline.set_text(_("Connecting..."))
          self.refresh_updates_count()
          self.hbox_offline.show()
          self.vbox_alerts.show()
          self.connected = False
      # in doubt (STATE_UNKNOWN), assume connected
      elif (state in NetworkManagerHelper.NM_STATE_CONNECTED_LIST or 
           state == NetworkManagerHelper.NM_STATE_UNKNOWN):
          self.refresh_updates_count()
          self.hbox_offline.hide()
          self.connected = True
          # trigger re-showing the current app to get changelog info (if needed)
          self.on_treeview_update_cursor_changed(self.treeview_update)
      else:
          self.connected = False
          self.label_offline.set_text(_("You may not be able to check for updates or download new updates."))
          self.refresh_updates_count()
          self.hbox_offline.show()
          self.vbox_alerts.show()
          
  def _on_battery_alert(self, watcher, on_battery):
      if on_battery:
          self.hbox_battery.show()
          self.vbox_alerts.show()
      else:
          self.hbox_battery.hide()    

  def _on_network_3g_alert(self, watcher, on_3g, is_roaming):
      #print("on 3g: %s; roaming: %s" % (on_3g, is_roaming))
      if is_roaming:
          self.hbox_roaming.show()
          self.hbox_on_3g.hide()
      elif on_3g:
          self.hbox_on_3g.show()
          self.hbox_roaming.hide()
      else:
          self.hbox_on_3g.hide()
          self.hbox_roaming.hide()
  def row_activated(self, treeview, path, column):
      iter = self.store.get_iter(path)
          
      pkg = self.store.get_value(iter, LIST_PKG)
      origin = self.store.get_value(iter, LIST_ORIGIN)
      if pkg is not None:
          return
      self.toggle_from_origin(pkg, origin, True)
  def toggle_from_origin(self, pkg, origin, select_all = True ):
      self.setBusy(True)
      actiongroup = apt_pkg.ActionGroup(self.cache._depcache)
      for pkg in self.list.pkgs[origin]:
          if pkg.marked_install or pkg.marked_upgrade:
              #print("marking keep: ", pkg.name)
              pkg.mark_keep()
          elif not (pkg.name in self.list.held_back):
              #print("marking install: ", pkg.name)
              pkg.mark_install(auto_fix=False,auto_inst=False)
      # check if we left breakage
      if self.cache._depcache.broken_count:
          Fix = apt_pkg.ProblemResolver(self.cache._depcache)
          Fix.resolve_by_keep()
      self.refresh_updates_count()
      self.treeview_update.queue_draw()
      del actiongroup
      self.setBusy(False)
  
  def toggled(self, renderer, path):
    """ a toggle button in the listview was toggled """
    iter = self.store.get_iter(path)
    pkg = self.store.get_value(iter, LIST_PKG)
    origin = self.store.get_value(iter, LIST_ORIGIN)
    # make sure that we don't allow to toggle deactivated updates
    # this is needed for the call by the row activation callback
    if pkg is None:
        toggled_value = not self.store.get_value(iter, LIST_TOGGLE_CHECKED)
        self.toggle_from_origin(pkg, origin, toggled_value)
        self.store.set_value(iter, LIST_TOGGLE_CHECKED, toggled_value )
        self.treeview_update.queue_draw()
        return
    if pkg is None or pkg.name in self.list.held_back:
        return False
    self.setBusy(True)
    # update the cache
    if pkg.marked_install or pkg.marked_upgrade:
        pkg.mark_keep()
        if self.cache._depcache.broken_count:
            Fix = apt_pkg.ProblemResolver(self.cache._depcache)
            Fix.resolve_by_keep()
    else:
        try:
            pkg.mark_install()
        except SystemError:
            pass
    self.treeview_update.queue_draw()
    self.refresh_updates_count()
    self.setBusy(False)

  def on_treeview_update_row_activated(self, treeview, path, column, *args):
    """
    If an update row was activated (by pressing space), toggle the 
    install check box
    """
    self.toggled(None, path)

  def exit(self):
    """ exit the application, save the state """
    self.save_state()
    #Gtk.main_quit()
    sys.exit(0)

  def save_state(self):
    """ save the state  (window-size for now) """
    if self.expander_details.get_expanded():
      (w, h) = self.window_main.get_size()
      self.settings.set_int("window-width", w)
      self.settings.set_int("window-height", h)

  def restore_state(self):
    """ restore the state (window-size for now) """
    w = self.settings.get_int("window-width")
    h = self.settings.get_int("window-height")
    if w > 0 and h > 0 and self.expander_details.get_expanded():
      self.window_main.resize(w, h)
    return False

  def fillstore(self):
    # use the watch cursor
    self.setBusy(True)
    # disconnect the view first
    self.treeview_update.set_model(None)
    self.store.clear()
    
    # clean most objects
    self.dl_size = 0
    try:
        self.initCache()
    except SystemError as e:
        msg = ("<big><b>%s</b></big>\n\n%s\n'%s'" %
               (_("Could not initialize the package information"),
                _("An unresolvable problem occurred while "
                  "initializing the package information.\n\n"
                  "Please report this bug against the 'update-manager' "
                  "package and include the following error message:\n"),
                e)
               )
        dialog = Gtk.MessageDialog(self.window_main,
                                   0, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.CLOSE,"")
        dialog.set_markup(msg)
        dialog.get_content_area().set_spacing(6)
        dialog.run()
        dialog.destroy()
        sys.exit(1)
    self.list = UpdateList(self)
    
    while Gtk.events_pending():
        Gtk.main_iteration()

    # fill them again
    try:
        self.list.update(self.cache)
    except SystemError as e:
        msg = ("<big><b>%s</b></big>\n\n%s\n'%s'" %
               (_("Could not calculate the upgrade"),
                _("An unresolvable problem occurred while "
                  "calculating the upgrade.\n\n"
                  "Please report this bug against the 'update-manager' "
                  "package and include the following error message:"),
                e)
               )
        dialog = Gtk.MessageDialog(self.window_main,
                                   0, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.CLOSE,"")
        dialog.set_markup(msg)
        dialog.get_content_area().set_spacing(6)
        dialog.run()
        dialog.destroy()
    if self.list.num_updates > 0:
      #self.treeview_update.set_model(None)
      self.scrolledwindow_update.show()
      origin_list = sorted(
        self.list.pkgs, key=operator.attrgetter("importance"), reverse=True)
      for origin in origin_list:
        self.store.append(['<b><big>%s</big></b>' % origin.description,
                           origin.description, None, origin,True])
        for pkg in self.list.pkgs[origin]:
          name = xml.sax.saxutils.escape(pkg.name)
          if not pkg.is_installed:
              name += _(" (New install)")
          summary = xml.sax.saxutils.escape(getattr(pkg.candidate, "summary", None))
          if self.summary_before_name:
              contents = "%s\n<small>%s</small>" % (summary, name)
          else:
              contents = "<b>%s</b>\n<small>%s</small>" % (name, summary)
          #TRANSLATORS: the b stands for Bytes
          size = _("(Size: %s)") % humanize_size(getattr(pkg.candidate, "size", 0))
          installed_version = getattr(pkg.installed, "version", None)
          candidate_version = getattr(pkg.candidate, "version", None)
          if installed_version is not None:
              version = _("From version %(old_version)s to %(new_version)s") %\
                  {"old_version" : installed_version,
                   "new_version" : candidate_version}
          else:
              version = _("Version %s") % candidate_version
          if self.show_versions:
              contents = "%s\n<small>%s %s</small>" % (contents, version, size)
          else:
              contents = "%s <small>%s</small>" % (contents, size)
          self.store.append([contents, pkg.name, pkg, None, True])
      self.treeview_update.set_model(self.store)
    self.update_count()
    self.setBusy(False)
    while Gtk.events_pending():
      Gtk.main_iteration()
    self.check_all_updates_installable()
    self.refresh_updates_count()
    return False

  def dist_no_longer_supported(self, meta_release):
    show_dist_no_longer_supported_dialog(self.window_main)

  def error(self, summary, details):
      " helper function to display a error message "
      msg = ("<big><b>%s</b></big>\n\n%s\n" % (summary, details) )
      dialog = Gtk.MessageDialog(self.window_main,
                                 0, Gtk.MessageType.ERROR,
                                 Gtk.ButtonsType.CLOSE,"")
      dialog.set_markup(msg)
      dialog.get_content_area().set_spacing(6)
      dialog.run()
      dialog.destroy()

  def on_button_dist_upgrade_clicked(self, button):
      #print("on_button_dist_upgrade_clicked")
      if self.new_dist.upgrade_broken:
          return self.error(
              _("Release upgrade not possible right now"),
              _("The release upgrade can not be performed currently, "
                "please try again later. The server reported: '%s'") % self.new_dist.upgrade_broken)
      fetcher = DistUpgradeFetcherGtk(new_dist=self.new_dist, parent=self, progress=GtkAcquireProgress(self, _("Downloading the release upgrade tool")))
      if self.options.sandbox:
          fetcher.run_options.append("--sandbox")
      fetcher.run()
      
  def new_dist_available(self, meta_release, upgradable_to):
    self.frame_new_release.show()
    self.label_new_release.set_markup(_("<b>New Ubuntu release '%s' is available</b>") % upgradable_to.version)
    self.new_dist = upgradable_to
    

  # fixme: we should probably abstract away all the stuff from libapt
  def initCache(self): 
    # get the lock
    try:
        apt_pkg.pkgsystem_lock()
    except SystemError:
        pass
        #d = Gtk.MessageDialog(parent=self.window_main,
        #                      flags=Gtk.DialogFlags.MODAL,
        #                      type=Gtk.MessageType.ERROR,
        #                      buttons=Gtk.ButtonsType.CLOSE)
        #d.set_markup("<big><b>%s</b></big>\n\n%s" % (
        #    _("Only one software management tool is allowed to "
        #      "run at the same time"),
        #    _("Please close the other application e.g. 'aptitude' "
        #      "or 'Synaptic' first.")))
        #print("error from apt: '%s'" % e)
        #d.set_title("")
        #res = d.run()
        #d.destroy()
        #sys.exit()

    try:
        if hasattr(self, "cache"):
            self.cache.open(self.progress)
            self.cache._initDepCache()
        else:
            self.cache = MyCache(self.progress)
    except AssertionError:
        # if the cache could not be opened for some reason,
        # let the release upgrader handle it, it deals
        # a lot better with this
        self.ask_run_partial_upgrade()
        # we assert a clean cache
        msg=("<big><b>%s</b></big>\n\n%s"% \
             (_("Software index is broken"),
              _("It is impossible to install or remove any software. "
                "Please use the package manager \"Synaptic\" or run "
                "\"sudo apt-get install -f\" in a terminal to fix "
                "this issue at first.")))
        dialog = Gtk.MessageDialog(self.window_main,
                                   0, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.CLOSE,"")
        dialog.set_markup(msg)
        dialog.get_content_area().set_spacing(6)
        dialog.run()
        dialog.destroy()
        sys.exit(1)
    else:
        self.progress.all_done()

  def check_all_updates_installable(self):
    """ Check if all available updates can be installed and suggest
        to run a distribution upgrade if not """
    if self.list.distUpgradeWouldDelete > 0:
        self.ask_run_partial_upgrade()

  def ask_run_partial_upgrade(self):
      self.dialog_dist_upgrade.set_transient_for(self.window_main)
      self.dialog_dist_upgrade.set_title("")
      res = self.dialog_dist_upgrade.run()
      self.dialog_dist_upgrade.hide()
      if res == Gtk.ResponseType.YES:
          os.execl("/usr/bin/gksu",
                   "/usr/bin/gksu", "--desktop",
                   "/usr/share/applications/update-manager.desktop",
                   "--", "/usr/bin/update-manager", "--dist-upgrade")
      return False

  def check_metarelease(self):
      " check for new meta-release information "
      settings = Gio.Settings("com.ubuntu.update-manager")
      self.meta = MetaRelease(self.options.devel_release,
                              self.options.use_proposed)
      self.meta.connect("dist_no_longer_supported",self.dist_no_longer_supported)
      # check if we are interessted in dist-upgrade information
      # (we are not by default on dapper)
      if (self.options.check_dist_upgrades or
          settings.get_boolean("check-dist-upgrades")):
          self.meta.connect("new_dist_available",self.new_dist_available)
      

  def main(self):
    # check for new distributin information
    self.check_metarelease()

    while Gtk.events_pending():
      Gtk.main_iteration()

    self.fillstore()
    self.alert_watcher.check_alert_state()
