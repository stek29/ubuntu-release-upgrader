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
import os.path


class DistUpgradeQuirks(object):
    """
    This class collects the various quirks handlers that can
    be hooked into to fix/work around issues that the individual
    releases have
    """
    
    def __init__(self, controller, config):
        self.controller = controller
        self.view = controller._view
        self.config = config

    def run(self, quirksName):
        """
        Run the specific quirks handler, the follow handlers are supported:
        - PreUpgrade: run before the sources.list is rewritten
        """
        funcname = "%s%s" % (self.config.get("Sources","To"), quirksName)
        #logging.debug("DistUpgradeQuirks.run() %s (%s)" % (quirksName, 
        #                                                   funcname))
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

    # intrepid quirks handlers -------------------------------------------
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

    # fglrx is broken in intrepid (no support for xserver 1.5)
    def intrepidPreUpgrade(self):
        " quirks that are run before the upgrade to intrepid "
        logging.debug("running intrepiPreUpgradeQuirks()")
        if self._checkForFglrx():
            res = self.view.askYesNoQuestion(_("Upgrading may reduce desktop "
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
        return
