# UpdatesAvailable.py
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
import stat
import re
import logging
import operator
import subprocess
import time
import threading
import xml.sax.saxutils

from .backend import get_backend

from gettext import gettext as _
from gettext import ngettext


from .Core.utils import (humanize_size,
                         on_battery,
                         inhibit_sleep,
                         allow_sleep)
from .Core.AlertWatcher import AlertWatcher

from DistUpgrade.DistUpgradeCache import NotEnoughFreeSpaceError

from .ChangelogViewer import ChangelogViewer
from .SimpleGtk3builderApp import SimpleGtkbuilderApp
from .UnitySupport import UnitySupport


#import pdb

# FIXME:
# - kill "all_changes" and move the changes into the "Update" class

# list constants
(LIST_CONTENTS, LIST_NAME, LIST_PKG, LIST_ORIGIN, LIST_TOGGLE_CHECKED) = range(5)

# NetworkManager enums
from .Core.roam import NetworkManagerHelper

class UpdatesAvailable(SimpleGtkbuilderApp):

  def __init__(self, app):
    self.window_main = app
    self.datadir = app.datadir
    self.options = app.options
    self.cache = app.cache
    self.list = app.update_list
    SimpleGtkbuilderApp.__init__(self, self.datadir+"gtkbuilder/UpdateManager.ui",
                                 "update-manager")

    # Used for inhibiting power management
    self.sleep_cookie = None
    self.sleep_dev = None

    # workaround for LP: #945536
    self.clearing_store = False

    self.button_close.grab_focus()
    self.dl_size = 0
    self.connected = True

    self.settings =  Gio.Settings("com.ubuntu.update-manager")

    # create text view
    self.textview_changes = ChangelogViewer()
    self.textview_changes.show()
    self.scrolledwindow_changes.add(self.textview_changes)
    changes_buffer = self.textview_changes.get_buffer()
    changes_buffer.create_tag("versiontag", weight=Pango.Weight.BOLD)

    # expander
    self.expander_details.set_expanded(self.settings.get_boolean("show-details"))
    self.expander_details.connect("activate", self.pre_activate_details)
    self.expander_details.connect("notify::expanded", self.activate_details)
    self.expander_desc.connect("notify::expanded", self.activate_desc)

    # useful exit stuff
    self.button_close.connect("clicked", lambda w: self.window_main.exit())

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

    # init show version
    self.show_versions = self.settings.get_boolean("show-versions")
    # init summary_before_name
    self.summary_before_name = self.settings.get_boolean("summary-before-name")

    # Create Unity launcher quicklist
    # FIXME: instead of passing parent we really should just send signals
    self.unity = UnitySupport(parent=self)
    
    # Alert watcher
    self.alert_watcher = AlertWatcher()
    self.alert_watcher.connect("network-alert", self._on_network_alert)
    self.alert_watcher.connect("battery-alert", self._on_battery_alert)
    self.alert_watcher.connect("network-3g-alert", self._on_network_3g_alert)

  def install_all_updates (self, menu, menuitem, data):
    self.select_all_updgrades (None)
    self.on_button_install_clicked (None)

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
              text_header = _("Updated software has been issued since Ubuntu %s was released. Do you want to install it now?") % self.window_main.meta_release.current_dist_version
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
    self.window_main.refresh_cache()
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
            self.window_main.start_error(err_sum, err_long % (req.size_total,
                                                              req.dir,
                                                              req.size_needed,
                                                              req.dir))
        return
    except SystemError as e:
        logging.exception("free space check failed")
    self.window_main.start_install()

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
    expanded = self.expander_details.get_expanded()
    self.window_main.set_resizable(expanded)
    if w > 0 and h > 0 and expanded:
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

  def main(self):
    self.window_main.push(self.pane_updates_available, self)
    self.fillstore()
    self.alert_watcher.check_alert_state()
