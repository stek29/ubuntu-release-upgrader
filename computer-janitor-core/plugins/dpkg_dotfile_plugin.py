# dpkg_dotfile_plugin.py - remove .dpkg-old/new files
# Copyright (C) 2009  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os

import computerjanitor
_ = computerjanitor.setup_gettext()


class DpkgDotfilePlugin(computerjanitor.Plugin):

    """Find .dpkg-old/new files.
    
    This plugin finds .dpkg-old and .dpkg-new files that dpkg creates
    when it handles conffiles. They are typically in /etc, but
    occasionally in some other locations, so we scan a list of directories
    known to have conffiles. Any regular files with a .dpkg-old or
    .dpkg-new suffix is added to the list.
    
    """

    cruft_description = _("File was left on the disk by dpkg as part of "
                          "its configuration file handling. If your computer "
                          "works fine, you can remove it. You may want to "
                          "compare it with the actual configuration file "
                          "(the one without the .dpkg-old or .dpkg-new "
                          "suffix). If unsure, don't remove the file.")

    def __init__(self):
        # This is a list of directories that are known to contain, or have
        # contained, conffiles in Ubuntu dapper, hardy, intrepid, or jaunty
        # (as of Alpha 4). It should perhaps be updated periodically.
        self.dirs = ["/etc",
                     "/var/ax25",
                     "/var/cache/roxen4",
                     "/var/games",
                     "/var/lib/crafty",
                     "/var/lib/drac",
                     "/var/lib/firebird2",
                     "/var/lib/gnats",
                     "/var/lib/leksbot",
                     "/var/lib/linpopup",
                     "/var/lib/lxr-cvs",
                     "/var/lib/mason",
                     "/var/lib/roxen4",
                     "/var/lib/sysnews",
                     "/var/list",
                     "/var/spool/fcron",
                     "/var/spool/hylafax/bin",
                     "/var/yp"]

    def scan(self, dirname):
        """Scan one directory for crufty files."""
        list = []
        for dirname, dirnames, filenames in os.walk(dirname):
            filenames = [x for x in filenames 
                         if x.endswith(".dpkg-old") or
                            x.endswith(".dpkg-new")]
            filenames = [os.path.join(dirname, x) for x in filenames]
            filenames = [x for x in filenames 
                         if os.path.isfile(x) and not os.path.islink(x)]
            list += filenames
        return list

    def get_cruft(self):
        list = []
        for dir in self.dirs:
            list += self.scan(dir)
        return [computerjanitor.FileCruft(x, self.cruft_description) 
                for x in list]
