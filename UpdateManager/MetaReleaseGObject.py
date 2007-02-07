#  Copyright (c) 2004-2007 Canonical
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

import pygtk
pygtk.require('2.0')
import gobject
import thread
import urllib2
import os
import string
import apt_pkg
import time
import rfc822
from subprocess import Popen,PIPE
from MetaRelease import MetaReleaseCore

class MetaRelease(MetaReleaseCore,gobject.GObject):

    __gsignals__ = { 
        'new_dist_available' : (gobject.SIGNAL_RUN_LAST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
        'dist_no_longer_supported' : (gobject.SIGNAL_RUN_LAST,
                                      gobject.TYPE_NONE,
                                      ())

        }

    def __init__(self, useDevelopmentRelase=False, useProposed=False):
        gobject.GObject.__init__(self)
        MetaReleaseCore.__init__(self, useDevelopmentRelase, useProposed)

    def dist_no_longer_supported(self, dist):
        self.emit("dist_no_longer_supported",dist)

    def new_dist_available(self, dist):
        self.emit("new_dist_available",dist)


