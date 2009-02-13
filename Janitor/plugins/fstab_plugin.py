# fstab_plugin.py - modify /etc/fstab to be similar to fresh install
# Copyright (C) 2008  Canonical, Ltd.
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


import fstab

import computerjanitor
_ = computerjanitor.setup_gettext()


class RelatimeCruft(computerjanitor.Cruft):

    """Cruft consisting of a missing 'relatime' option for a filesystem."""

    def __init__(self, fstab_line):
        self.fstab_line = fstab_line
        
    def get_prefix(self):
        return "relatime"
        
    def get_prefix_description(self):
        return "fstab mount option relatime missing"
        
    def get_shortname(self):
        return self.fstab_line.directory
        
    def get_description(self):
        return _("The 'relatime' mount option is missing for filesystem "
                "mounted at %s") % self.fstab_line.directory
                
    def cleanup(self):
        if "relatime" not in self.fstab_line.options:
            self.fstab_line.options += ["relatime"]


class FstabPlugin(computerjanitor.Plugin):

    """Plugin to modify /etc/fstab.
    
    This plugin will add the relatime mount option to /etc/fstab
    to those ext2 and ext3 filesystems that are missing it.
    
    In the future, it may do other things. We'll see. The goal is
    to provide a way to add tweaks to /etc/fstab upon upgraded that
    would be there if the system was installed from scratch.
    
    """
    
    allowed_fstypes = ["ext2", "ext3"]
    
    def __init__(self):
        self.fstab_filename = "/etc/fstab"
        self.fstab = None
        
    def get_cruft(self):
        self.fstab = fstab.Fstab()
        self.fstab.read(self.fstab_filename)
        cruft = []
        for line in self.fstab.lines:
            if line.fstype in self.allowed_fstypes:
                if "relatime" not in line.options:
                    if "noatime" not in line.options:
                        cruft.append(RelatimeCruft(line))
        return cruft

    def post_cleanup(self):
        self.fstab.write(self.fstab_filename)
