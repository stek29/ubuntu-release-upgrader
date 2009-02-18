# landscape_stub_plugin.py
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


class LandscapePackageCruft(computerjanitor.PackageCruft):
    def __init__(self, app, pkg, description):
        computerjanitor.PackageCruft.__init__(self, pkg, description)
        self.app = app
    
    def cleanup(self):
        self.app.apt_cache.markRemove(self._pkg.name, 
                                  "custom landscape stub removal rule")
        if self.app.apt_cache.has_key("landscape-common"):
            self.app.apt_cache["landscape-common"].markKeep()
            self.app.apt_cache.markInstall("landscape-common", 
                                       "custom landscape-common stub install rule (to ensure its nor marked for auto-remove)")

class LandscapeStubPlugin(computerjanitor.Plugin):

    """Plugin to remove landscape-client (in desktop mode).
       It was a stub anyway and is more useful on the server """

    description = _("Remove landscape-client stub")

    def __init__(self):
        self.condition = ["from_hardyPostDistUpgradeCache"]

    def get_cruft(self):
        if not hasattr(self.app, "serverMode"): # pragma: no cover
            return
        name = "landscape-client"
        ver = "0.1"
        if not self.app.serverMode:
            if (self.app.apt_cache.has_key(name) and
                self.app.apt_cache[name].installedVersion == ver):
                yield LandscapePackageCruft(self.app,
                                            self.app.apt_cache[name],
                                            self.description)
