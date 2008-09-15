# DistUpgradeGettext.py - safe wrapper around gettext
#  
#  Copyright (c) 2008 Canonical
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


import gettext as mygettext

def gettext(message):
    """
    version of gettext that logs errors but does not crash on incorrect
    number of arguments
    """
    try:
        return mygettext.gettext(message)
    except TypeError, e:
        logging.error("got exception '%s' from incorrect translation for message '%s'" % (e, msg))
        return message

def ngettext(msgid1, msgid2, n):
    """
    version of ngettext that logs errors but does not crash on incorrect
    number of arguments
    """
    try:
        return mygettext.ngettext(msgid1, msgid2, n)
    except TypeError, e:
        logging.error("got exception '%s' from incorrect ngettext translation for message '%s' '%s' %i" % (e, msgid1, msgid2, n))
        # dumb fallback to not crash
        if n == 1:
            return msgid1
        return msgid2
