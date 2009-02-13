# autoremoval_plugin.py - remove packages apt has marked as auto-removable
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


import os

import computerjanitor
_ = computerjanitor.setup_gettext()


class AutoRemovablePlugin(computerjanitor.Plugin):

    """Plugin for finding packages apt says are removable.
    
    Automatically removable packages are those that apt installed because
    they were dependencies of something else, but which the user never
    asked for specifically, and which further are no longer used by
    anything, hopefully also not by the user.
    
    """

    description = _("Package was installed because another package "
                    "required it, but now nothing requires it anymore.")

    def get_cruft(self):
        for pkg in self.app.apt_cache:
            if pkg.isAutoRemovable:
                yield computerjanitor.PackageCruft(pkg, self.description)
