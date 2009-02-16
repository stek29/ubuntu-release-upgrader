# check_admin_group_plugin.py - check current sudo user is in admin group
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


import grp
import os
import subprocess

import computerjanitor
_ = computerjanitor.setup_gettext()


class AdminGroupCruft(computerplugin.Cruft):

    """Create admin group, if missing, and add user to it."""
        
    def __init__(self, username):
        self.username = username
        
    def get_prefix(self):
        return "admingroup"
        
    def get_prefix_description(self):
        return "User is missing from admin group."
        
    def get_shortname(self):
        return self.username
        
    def get_description(self):
        return _("User %s needs to be added to the admin group.") % \
                self.username
                
    def cleanup(self):
        try:
            grp.getgrnam("admin")
        except KeyError:
            subprocess.call(["addgroup","--system","admin"])

        # double paranoia
        try:
            grp.getgrnam("admin")
        except KeyError:
            raise Exception("Creating admin group failed")
            
        cmd = ["usermod", "-a", "-G", "admin", self.username]
        res = subprocess.call(cmd)
        if res != 0:
            raise Exception("usermod failed to add %s to admin group" %
                            self.username)



class CheckAdminGroupPlugin(computerjanitor.Plugin):

    """Plugin to check the current sudo user is in the admin group."""

    description = _("User %s needs to be added to the admin group.")

    def get_cruft(self):
        if "SUDO_USER" in os.environ:
            username = os.environ["SUDO_USER"]

            try:
                admin_group = grp.getgrnam("admin").gr_mem
            except KeyError, e:
                logging.warning("System has no admin group (%s)" % e)
                yield AdminGroupCruft(username)
            else:
                if username not in admin_group:
                    yield AdminGroupCruft(username)
