# unsupported_plugin.py - remove packages no longer supported by Canonical
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


class UnsupportedPackagesPlugin(computerjanitor.Plugin):

    """Plugin to find packages no longer supported by Canonical.
    
    An unsupported package is one that is no longer available in the
    archive.
    
    Unfortunately, this heuristic is unable to treat packages installed
    manually (via dpkg), or from sources (such as PPAs) that are no longer
    in sources.list.

    """
    
    description = _("Package is no longer supported: it is no longer in the "
                    "package archive. (It may also have been installed from "
                    "an unofficial archive that is no longer available. In "
                    "that case you may want to keep it.)")

    basenames = ["linux-image", "linux-headers", "linux-image-debug",
                 "linux-ubuntu-modules", "linux-header-lum",
                 "linux-backport-modules",
                 "linux-header-lbm", "linux-restricted-modules"]

    def __init__(self):
        self.uname = os.uname()[2]

    def is_current_kernel(self, pkg):
        """Is pkg the currently running kernel or a related package?

        We don't want to remove the currently running kernel. The
        kernel packages have names that start with the strings in
        self.basenames, and end with the 'release' string from
        os.uname.

        """

        # FIXME: This code is based on that in update-manager. It
        # should be shared, but that's impractical to arrange in an
        # SRU.

        for base in self.basenames:
            if pkg.name == "%s-%s" % (base, self.uname):
                return True
                                 
        return False

    def is_supported(self, pkg):
    	"""Is a package supported?"""

        # FIXME: we do not have a way right now to tell if a package
        #        got manually installed or comes from a source (e.g. a PPA)
        #        that was once part of the system and later got disabled

    	if not pkg.isInstalled:
    	    return True
        if pkg.installedDownloadable or pkg.candidateDownloadable:
            return True
        if len(pkg._pkg.VersionList) > 1:
            # if there is just a single version and that is not
            # downloadable anymore, then its cruft this avoids cases
            # where the user has e.g. a newer version installed from a
            # ppa that is no longer downloadable, but the main archive
            # has the version still
            return True
        if self.is_current_kernel(pkg):
            # The currently running kernel is always supported. So there.
            return True
        return False

    def get_cruft(self):
        for pkg in self.app.apt_cache:
            if not self.is_supported(pkg):
                yield computerjanitor.PackageCruft(pkg, self.description)
