# DistUpgradeQuirks.py 
#  
#  Copyright (c) 2004-2008 Canonical
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

import logging
import os
import os.path
import shutil
import sys


class DistUpgradeQuirks(object):
    """
    This class collects the various quirks handlers that can
    be hooked into to fix/work around issues that the individual
    releases have
    """
    
    def __init__(self, controller, config):
        self.controller = controller
        self._view = controller._view
        self.config = config
        
    # the quirk function have the name:
    #  $todist$Name (e.g. intrepidPostUpgrade)
    #  $from_$fromdist$Name (e.g. from_dapperPostUpgrade)
    def run(self, quirksName):
        """
        Run the specific quirks handler, the follow handlers are supported:
        - PostInitialUpdate: run *before* the sources.list is rewritten but
                             after a initial apt-get update
        - PostUpgrade: run *after* the upgrade is finished successfully and 
                       packages got installed
        """
        # run the quirksHandler to-dist
        funcname = "%s%s" % (self.config.get("Sources","To"), quirksName)
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

        # now run the quirksHandler from_${FROM-DIST}Quirks
        funcname = "from_%s%s" % (self.config.get("Sources","From"), quirksName)
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

    # individual quirks handler ----------------------------------------
    def from_dapperPostUpgrade(self):
        " this works around quirks for dapper->hardy upgrades "
        logging.debug("running Controller.from_dapperQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()
        
    def intrepidPostUpgrade(self):
        " this applies rules for the hardy->intrepid upgrade "
	logging.debug("running Controller.intrepidQuirks handler")
        self._addRelatimeToFstab()

    def gutsyPostUpgrade(self):
        """ this function works around quirks in the feisty->gutsy upgrade """
        logging.debug("running Controller.gutsyQuirks handler")

    def feistyPostUpgrade(self):
        """ this function works around quirks in the edgy->feisty upgrade """
        logging.debug("running Controller.feistyQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()

    # fglrx is broken in intrepid (no support for xserver 1.5)
    def intrepidPostInitialUpdate(self):
        " quirks that are run before the upgrade to intrepid "
        logging.debug("running %s" %  sys._getframe().f_code.co_name
)
        if self._checkForFglrx():
            res = self._view.askYesNoQuestion(_("Upgrading may reduce desktop "
                                        "effects, and performance in games "
                                        "and other graphically intensive "
                                        "programs."),
                                      _("This computer is currently using "
                                        "the AMD 'fglrx' graphics driver. "
                                        "No version of this driver is "
                                        "available that works with Ubuntu "
                                        "8.10.\n\nDo you want to continue?"))
            if res == False:
                self.controller.abort()


    # helpers
    def _addRelatimeToFstab(self):
        " add the relatime option to ext2/ext3 filesystems on upgrade "
        logging.debug("_addRelatime")
        replaced = False
        lines = []
        # we have one cdrom to convert
        for line in open("/etc/fstab"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception, e:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            if (("ext2" in fstype or
                "ext3" in fstype) and 
                not "relatime" in options):
                logging.debug("adding 'relatime' to line '%s' " % line)
                line = line.replace(options,"%s,relatime" % options)
                logging.debug("replaced line is '%s' " % line)
                replaced=True
            lines.append(line)
        # we have converted a line (otherwise we would have exited already)
        if replaced:
            logging.debug("writing new /etc/fstab")
            open("/etc/fstab.intrepid","w").write("\n".join(lines))
            os.rename("/etc/fstab.intrepid","/etc/fstab")
        return True
        

    def _rewriteFstab(self):
        " convert /dev/{hd?,scd0} to /dev/cdrom for the feisty upgrade "
        logging.debug("_rewriteFstab()")
        replaced = 0
        lines = []
        # we have one cdrom to convert
        for line in open("/etc/fstab"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception, e:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            # edgy kernel has /dev/cdrom -> /dev/hd?
            # feisty kernel (for a lot of chipsets) /dev/cdrom -> /dev/scd0
            # this breaks static mounting (LP#86424)
            #
            # we convert here to /dev/cdrom only if current /dev/cdrom
            # points to the device in /etc/fstab already. this ensures
            # that we don't break anything or that we get it wrong
            # for systems with two (or more) cdroms. this is ok, because
            # we convert under the old kernel
            if ("iso9660" in fstype and
                device != "/dev/cdrom" and
                os.path.exists("/dev/cdrom") and
                os.path.realpath("/dev/cdrom") == device
                ):
                logging.debug("replacing '%s' " % line)
                line = line.replace(device,"/dev/cdrom")
                logging.debug("replaced line is '%s' " % line)
                replaced += 1
            lines.append(line)
        # we have converted a line (otherwise we would have exited already)
        if replaced > 0:
            logging.debug("writing new /etc/fstab")
            shutil.copy("/etc/fstab","/etc/fstab.edgy")
            open("/etc/fstab","w").write("\n".join(lines))
        return True

    def _checkAdminGroup(self):
        " check if the current sudo user is in the admin group "
        logging.debug("_checkAdminGroup")
        import grp
        try:
            admin_group = grp.getgrnam("admin").gr_mem
        except KeyError, e:
            logging.warning("System has no admin group (%s)" % e)
            subprocess.call(["addgroup","--system","admin"])
        # double paranoia
        try:
            admin_group = grp.getgrnam("admin").gr_mem
        except KeyError, e:
            logging.warning("adding the admin group failed (%s)" % e)
            return
        # if the current SUDO_USER is not in the admin group
        # we add him - this is no security issue because
        # the user is already root so adding him to the admin group
        # does not change anything
        if (os.environ.has_key("SUDO_USER") and
            not os.environ["SUDO_USER"] in admin_group):
            admin_user = os.environ["SUDO_USER"]
            logging.info("SUDO_USER=%s is not in admin group" % admin_user)
            cmd = ["usermod","-a","-G","admin",admin_user]
            res = subprocess.call(cmd)
            logging.debug("cmd: %s returned %i" % (cmd, res))

    def _checkForFglrx(self):
        " check if the fglrx driver is in use "
        XORG="/etc/X11/xorg.conf"
        if not os.path.exists(XORG):
            return False
        for line in open(XORG):
            s=line.split("#")[0].strip()
            # check for fglrx driver entry
            if (s.startswith("Driver") and
                s.endswith('"fglrx"')):
                return True
        return False
        
