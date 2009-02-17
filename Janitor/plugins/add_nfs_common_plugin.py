# add_nfs_common_plugin.py - install nfs-common if nfs is used
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
import logging
import os
import subprocess

import computerjanitor
_ = computerjanitor.setup_gettext()


class AddNfsCommonPlugin(computerjanitor.Plugin):

    """Plugin to install missing nfs-common package, if nfs is being used.
    
    This is a fix for the feisty->gutsy transition of utils-linux to
    nfs-common. See also LP: #141559.
    
    """

    description = _("NFS is being used, so the nfs-common package needs "
                    "to be installed.")

    def get_cruft(self):
        if "nfs-common" not in self.app.apt_cache:
            logging.warning("nfs-common package not available")
            return
        pkg = self.app.apt_cache["nfs-common"]
        try:
            for line in map(string.strip, open("/proc/mounts")):
                if line == '' or line.startswith("#"):
                    continue
                try:
                    (device, mount_point, fstype, options, a, b) = line.split()
                except Exception, e:
                    logging.error("can't parse line '%s'" % line)
                    continue
                if "nfs" in fstype and not pkg.isInstalled:
                    logging.debug("found nfs mount in line '%s', "
                                  "marking nfs-common for install " % line)
                    yield computerjanitor.MissingPackageCruft(pkg)
                    break
        except Exception, e:
            logging.warning("problem while transitioning "
                            "util-linux -> nfs-common (%s)" % e)
