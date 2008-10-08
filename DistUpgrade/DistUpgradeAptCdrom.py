# DistUpgradeAptCdrom.py 
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

import re
import os
import apt_pkg
import logging
import gzip
import shutil

from gettext import gettext as _


class AptCdromError(Exception):
    " base exception for apt cdrom errors "
    pass

class AptCdrom(object):
    " represents a apt cdrom object "

    def __init__(self, view, path):
        self.view = view
        self.cdrompath = path
        # the directories we found on disk with signatures, packages and i18n
        self.packagesdirs = set()
        self.sigdirs = set()
        self.i18ndirs = set()

    def restoreBackup(self, backup_ext):
        " restore the backup copy of the cdroms.list file (*not* sources.list)! "
        cdromstate = os.path.join(apt_pkg.Config.FindDir("Dir::State"),
                                  apt_pkg.Config.Find("Dir::State::cdroms"))
        if os.path.exists(cdromstate+backup_ext):
            shutil.copy(cdromstate+backup_ext, cdromstate)
        # mvo: we don't have to care about restoring the sources.list here because
        #      aptsources will do this for us anyway
        

    def _scanCD(self):
        """ 
        scan the CD for interessting files and return them as:
        (packagesfiles, signaturefiles, i18nfiles)
        """
        pass

    def _doAdd(self):
        " reimplement pkgCdrom::Add() in python "
        # os.walk() will not follow symlinks so we don't need
        # pkgCdrom::Score() and not dropRepeats() that deal with
        # killing the links
        for root, dirs, files in os.walk(self.cdrompath, topdown=True):
            if root.endswith("debian-installer"):
                del dirs[:]
                continue
            elif  ".aptignr" in files:
                continue
            elif "Packages" in files or "Packages.gz" in files:
                print "found Packages in ", root
                packagesdir.add(root)
            elif "Sources" in files or "Sources.gz" in files:
                logging.error("Sources entry found in %s but not supported" % root)
            elif "Release.gpg" in files:
                print "found Release{.gpg} ", root
                sigdir = set()
            elif "i18n" in dirs:
                print "found translations", root
                i18ndir = set()
            # there is nothing under pool but deb packages (no
            # indexfiles, so we skip that here
            elif os.path.split(root)[1] == ("pool"):
                del dirs[:]
        # now go over the packagesdirs and drop stuff that is not
        # our binary-$arch 
        arch = apt_pkg.Config.Find("APT::Architecture")
        for d in set(packagesdir):
            if "/binary-" in d and not arch in d:
                packagesdir.remove(d)
        if len(packagesdir) == 0:
            logging.error("no useable indexes found on CD, wrong ARCH?")
            raise AptCdromError, _("Unable to locate any package files, perhaps this is not a Ubuntu Disc or the wrong architecture?")
        # now generate a sources.list line
        info = os.path.join(self.cdrompath, ".disk","info")
        if os.path.exists(info):
            diskname = open(info).read()
            for special in ('"',']','[','_'):
                diskname = diskname.replace(special,'_')
        else:
            logging.error("no .disk/ directory found")
            return False

        # see apts indexcopy.cc:364 for details
        path = ""                                    
        dist = ""
        comps = []
        for d in packagesdir:
            # match(1) is the path, match(2) the dist
            # and match(3) the components
            m = re.match("(.*)/dists/([^/]*)/(.*)/binary-*", d)
            if not m:
                raise AptCdromError, _("Could not calculate sources.list entry")
            path = m.group(1)
            dist = m.group(2)
            comps.append(m.group(3))
        # entry to the sources.lisst
        pentry = "deb cdrom:[%s]/ %s %s" % (diskname, dist, " ".join(comps))

        # CopyPackages()
        for dir in packagesdir:
            fname = apt_pkg.URItoFileName("cdrom:[%s]/%sPackages" % (diskname,d[len(path)+1:]+"/"))
            outf = apt_pkg.Config.FindDir("Dir::State::lists")+fname
            inf = os.path.join(d,"Packages")
            if os.path.exists(inf):
                shutil.copy(inf,outf)
            elif os.path.exists(inf+".gz"):
                f=gzip.open(inf+".gz")
                out=open(outf,"w")
                # uncompress in 64k chunks
                while True:
                    s=f.read(64000)
                    out.write(s)
                    if s == "":
                        break
        # CopyAndVerify()
        

        # add CD to cdroms.list
        # update sources.list
        return True

    def add(self, backup_ext=None):
        " add a cdrom to apt's database "
        logging.debug("AptCdrom.add() called with '%s'", self.cdrompath)
        # do backup (if needed) of the cdroms.list file
        if backup_ext:
            cdromstate = os.path.join(apt_pkg.Config.FindDir("Dir::State"),
                                      apt_pkg.Config.Find("Dir::State::cdroms"))
            if os.path.exists(cdromstate):
                shutil.copy(cdromstate, cdromstate+backup_ext)
        # do the actual work
        apt_pkg.Config.Set("Acquire::cdrom::mount",self.cdrompath)
        apt_pkg.Config.Set("APT::CDROM::NoMount","true")
        cdrom = apt_pkg.GetCdrom()
        # FIXME: add cdrom progress here for the view
        progress = self.view.getCdromProgress()
        try:
            res = cdrom.Add(progress)
        except (SystemError, AptCdromError), e:
            logging.error("can't add cdrom: %s" % e)
            self.view.error(_("Failed to add the CD"),
                             _("There was a error adding the CD, the "
                               "upgrade will abort. Please report this as "
                               "a bug if this is a valid Ubuntu CD.\n\n"
                               "The error message was:\n'%s'") % e)
            return False
        logging.debug("AptCdrom.add() returned: %s" % res)
        return res

    def __nonzero__(self):
        """ helper to use this as 'if cdrom:' """
        return self.cdrompath is not None
