# GtkProgress.py 
#  
#  Copyright (c) 2004,2005 Canonical
#  
#  Author: Michael Vogt <michael.vogt@ubuntu.com>
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

from gi.repository import Gtk, Gdk
import apt
import apt_pkg
from gettext import gettext as _
from .Core.utils import humanize_size

class GtkAcquireProgress(apt.progress.base.AcquireProgress):
    def __init__(self, parent, summary="", descr=""):
        # if this is set to false the download will cancel
        self._continue = True
        # init vars here
        # FIXME: find a more elegant way, this sucks
        self.summary = parent.label_fetch_summary
        self.status = parent.label_fetch_status
        # we need to connect the signal manual here, it won't work
        # from the main window auto-connect
        parent.button_fetch_cancel.connect(
            "clicked", self.on_button_fetch_cancel_clicked)
        self.progress = parent.progressbar_fetch
        self.window_fetch = parent.window_fetch
        self.window_fetch.set_transient_for(parent.window_main)
        self.window_fetch.realize()
        self.window_fetch.get_window().set_functions(Gdk.WMFunction.MOVE)
        # set summary
        if summary != "":
            self.summary.set_markup("<big><b>%s</b></big> \n\n%s" %
                                    (summary, descr))
    def start(self):
        self.progress.set_fraction(0)
        self.window_fetch.show()
    def stop(self):
        self.window_fetch.hide()
    def on_button_fetch_cancel_clicked(self, widget):
        self._continue = False
    def pulse(self, owner):
        apt.progress.base.AcquireProgress.pulse(self, owner)
        current_item = self.current_items + 1
        if current_item > self.total_items:
          current_item = self.total_items
        if self.current_cps > 0:
            status_text = (_("Downloading file %(current)li of %(total)li with "
                             "%(speed)s/s") % {"current" : current_item,
                                               "total" : self.total_items,
                                               "speed" : humanize_size(self.current_cps)})
        else:
            status_text = (_("Downloading file %(current)li of %(total)li") % \
                           {"current" : current_item,
                            "total" : self.total_items })
            self.progress.set_fraction((self.current_bytes + self.current_items) /
                                       float(self.total_bytes + self.total_items))
        self.status.set_markup("<i>%s</i>" % status_text)
        # TRANSLATORS: show the remaining time in a progress bar:
        #if self.current_cps > 0:
        #    eta = ((self.total_bytes + self.current_bytes) / float(self.current_cps))
        #else:
        #    eta = 0.0
        #self.progress.set_text(_("About %s left" % (apt_pkg.TimeToStr(eta))))
        # FIXME: show remaining time
        self.progress.set_text("")

        while Gtk.events_pending():
            Gtk.main_iteration()
        return self._continue

if __name__ == "__main__":
    import apt
    from .SimpleGtkbuilderApp import SimpleGtkbuilderApp

    class MockParent(SimpleGtkbuilderApp):
        """Mock parent for the fetcher that just loads the UI file"""
        def __init__(self):
            SimpleGtkbuilderApp.__init__(self, "../data/gtkbuilder/UpdateManager.ui", "update-manager")

    # create mock parent and fetcher
    parent = MockParent()
    acquire_progress = GtkAcquireProgress(parent, "summary", "long detailed description")
    #acquire_progress = GtkAcquireProgress(parent)

    # download lists
    cache = apt.Cache()
    res = cache.update(acquire_progress)
    # generate a dist-upgrade (to feed data to the fetcher) and get it
    cache.upgrade()
    pm = apt_pkg.PackageManager(cache._depcache)
    fetcher = apt_pkg.Acquire(acquire_progress)
    res = cache._fetch_archives(fetcher, pm)
    print(res)
    
    
