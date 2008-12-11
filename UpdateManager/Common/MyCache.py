# MyCache.py 
#  
#  Copyright (c) 2004-2008 Canonical
#  
#  Author: Michael Vogt <mvo@debian.org>
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

import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)
import apt
import apt_pkg
import os
import DistUpgrade.DistUpgradeCache
from DistUpgrade.DistUpgradeCache import NotEnoughFreeSpaceError

SYNAPTIC_PINFILE = "/var/lib/synaptic/preferences"
CHANGELOGS_URI="http://changelogs.ubuntu.com/changelogs/pool/%s/%s/%s/%s_%s/changelog"


class MyCache(DistUpgrade.DistUpgradeCache.MyCache):
    def __init__(self, progress, rootdir=None):
        apt.Cache.__init__(self, progress, rootdir)
        # raise if we have packages in reqreinst state
        # and let the caller deal with that (runs partial upgrade)
        assert len(self.reqReinstallPkgs) == 0
        # init the regular cache
        self._initDepCache()
        self.all_changes = {}
        # on broken packages, try to fix via saveDistUpgrade()
        if self._depcache.BrokenCount > 0:
            self.saveDistUpgrade()
        assert (self._depcache.BrokenCount == 0 and 
                self._depcache.DelCount == 0)

    def _initDepCache(self):
        #apt_pkg.Config.Set("Debug::pkgPolicy","1")
        #self.depcache = apt_pkg.GetDepCache(self.cache)
        #self._depcache = apt_pkg.GetDepCache(self._cache)
        self._depcache.ReadPinFile()
        if os.path.exists(SYNAPTIC_PINFILE):
            self._depcache.ReadPinFile(SYNAPTIC_PINFILE)
        self._depcache.Init()
    def clear(self):
        self._initDepCache()
    @property
    def requiredDownload(self):
        """ get the size of the packages that are required to download """
        pm = apt_pkg.GetPackageManager(self._depcache)
        fetcher = apt_pkg.GetAcquire()
        pm.GetArchives(fetcher, self._list, self._records)
        return fetcher.FetchNeeded
    @property
    def installCount(self):
        return self._depcache.InstCount
    def saveDistUpgrade(self):
        """ this functions mimics a upgrade but will never remove anything """
        self._depcache.Upgrade(True)
        wouldDelete = self._depcache.DelCount
        if self._depcache.DelCount > 0:
            self.clear()
        assert self._depcache.BrokenCount == 0 and self._depcache.DelCount == 0
        self._depcache.Upgrade()
        return wouldDelete
    def matchPackageOrigin(self, pkg, matcher):
        """ match 'pkg' origin against 'matcher', take versions between
            installedVersion and candidateVersion into account too
            Useful if installed pkg A v1.0 is available in both
            -updates (as v1.2) and -security (v1.1). we want to display
            it as a security update then
        """
        inst_ver = pkg._pkg.CurrentVer
        cand_ver = self._depcache.GetCandidateVer(pkg._pkg)
        # init with empty match
        update_origin = matcher[(None,None)]
        for ver in pkg._pkg.VersionList:
            # discard is < than installed ver
            if (inst_ver and
                apt_pkg.VersionCompare(ver.VerStr, inst_ver.VerStr) <= 0):
                #print "skipping '%s' " % ver.VerStr
                continue
            # check if we have a match
            for(verFileIter,index) in ver.FileList:
                if matcher.has_key((verFileIter.Archive, verFileIter.Origin)):
                    indexfile = pkg._list.FindIndex(verFileIter)
                    if indexfile: # and indexfile.IsTrusted:
                        match = matcher[verFileIter.Archive, verFileIter.Origin]
                        if match.importance > update_origin.importance:
                            update_origin = match
        return update_origin
        
    def get_changelog(self, name, lock):
        # don't touch the gui in this function, it needs to be thread-safe
        pkg = self[name]

        # get the src package name
        srcpkg = pkg.sourcePackageName

        # assume "main" section 
        src_section = "main"
        # use the section of the candidate as a starting point
        section = pkg._depcache.GetCandidateVer(pkg._pkg).Section

        # get the source version, start with the binaries version
        binver = pkg.candidateVersion
        srcver = pkg.candidateVersion
        #print "bin: %s" % binver

        l = section.split("/")
        if len(l) > 1:
            src_section = l[0]

        # lib is handled special
        prefix = srcpkg[0]
        if srcpkg.startswith("lib"):
            prefix = "lib" + srcpkg[3]

        # stip epoch, but save epoch for later when displaying the
        # launchpad changelog
        srcver_epoch = srcver
        l = string.split(srcver,":")
        if len(l) > 1:
            srcver = "".join(l[1:])

        try:
            uri = CHANGELOGS_URI % (src_section,prefix,srcpkg,srcpkg, srcver)
            # print "Trying: %s " % uri
            changelog = urllib2.urlopen(uri)
            #print changelog.read()
            # do only get the lines that are new
            alllines = ""
            regexp = "^%s \((.*)\)(.*)$" % (re.escape(srcpkg))

            i=0
            while True:
                line = changelog.readline()
                if line == "":
                    break
                match = re.match(regexp,line)
                if match:
                    # strip epoch from installed version
                    # and from changelog too
                    installed = pkg.installedVersion
                    if installed and ":" in installed:
                        installed = installed.split(":",1)[1]
                    changelogver = match.group(1)
                    if changelogver and ":" in changelogver:
                        changelogver = changelogver.split(":",1)[1]
                    # we test for "==" here to ensure that the version
                    # is actually really in the changelog - if not
                    # just display it all, this catches cases like:
                    # gcc-defaults with "binver=4.3.1" and srcver=1.76
                    if (installed and 
                        apt_pkg.VersionCompare(changelogver,installed)==0):
                        break
                alllines = alllines + line

            # Print an error if we failed to extract a changelog
            if len(alllines) == 0:
                alllines = _("The changelog does not contain any relevant changes.\n\n"
                             "Please use http://launchpad.net/ubuntu/+source/%s/%s/+changelog\n"
                             "until the changes become available or try again "
                             "later.") % (srcpkg, srcver_epoch),
            # only write if we where not canceld
            if lock.locked():
                self.all_changes[name] = [alllines, srcpkg]
        except urllib2.HTTPError, e:
            if lock.locked():
                self.all_changes[name] = [
                    _("The list of changes is not available yet.\n\n"
                      "Please use http://launchpad.net/ubuntu/+source/%s/%s/+changelog\n"
                      "until the changes become available or try again "
                      "later.") % (srcpkg, srcver_epoch),
                    srcpkg]
        except (IOError, httplib.BadStatusLine, socket.error), e:
            print "caught exception: ", e
            if lock.locked():
                self.all_changes[name] = [_("Failed to download the list "
                                            "of changes. \nPlease "
                                            "check your Internet "
                                            "connection."), srcpkg]
        if lock.locked():
            lock.release()

