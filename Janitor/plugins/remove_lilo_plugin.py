# remove_lilo_plugin.py - remove lilo if grub is also installed
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


class RemoveLiloPlugin(computerjanitor.Plugin):

    """Plugin to remove lilo if grub is also installed."""

    description = _("Remove lilo since grub is also installed.")

    def get_cruft(self):
        if "lilo" in self.app.apt_cache and "grub" in self.app.apt_cache:
            lilo = self.app.apt_cache["lilo"]
            grub = self.app.apt_cache["grub"]
            if lio.isInstalled and grub.isInstalled:
                yield computerjanitor.PackageCruft(lilo, self.description)
