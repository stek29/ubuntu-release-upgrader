# ReleaseNotesViewer.py
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-
#
#  Copyright (c) 2011 Canonical
#
#  Author: Michael Vogt <mvo@ubutnu.com>
#
#  This modul provides an inheritance of the Gtk.TextView that is
#  aware of http URLs and allows to open them in a browser.
#  It is based on the pygtk-demo "hypertext".
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

from gi.repository import Gtk
from gi.repository import WebKit2

from .ReleaseNotesViewer import open_url


class ReleaseNotesViewerWebkit(WebKit2.WebView):
    def __init__(self, notes_url):
        super(ReleaseNotesViewerWebkit, self).__init__()
        self.load_uri(notes_url)
        self.connect("decide-policy",
                     self._on_decide_policy)

    def _on_decide_policy(self, web_view, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            navigation_action = decision.get_navigation_action()
            navigation_request = navigation_action.get_request()
            navigation_type = navigation_action.get_navigation_type()

            if navigation_type == WebKit2.NavigationType.LINK_CLICKED:
                uri = navigation_request.get_uri()
                open_url(uri)
                decision.ignore()
                return True

        return False


if __name__ == "__main__":
    win = Gtk.Window()
    win.set_size_request(600, 400)
    scroll = Gtk.ScrolledWindow()
    rv = ReleaseNotesViewerWebkit("http://archive.ubuntu.com/ubuntu/dists/"
                                  "devel/main/dist-upgrader-all/current/"
                                  "ReleaseAnnouncement.html")
    scroll.add(rv)
    win.add(scroll)
    win.show_all()
    Gtk.main()
