# MetaRelease.py 
#  
#  Copyright (c) 2004,2005 Canonical
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

import thread
import urllib2
import os
import string
import apt_pkg
import time
import rfc822
from subprocess import Popen,PIPE

class Dist(object):
    def __init__(self, name, version, date, supported):
        self.name = name
        self.version = version
        self.date = date
        self.supported = supported
        self.releaseNotesURI = None
        self.upgradeTool = None
        self.upgradeToolSig = None

class MetaReleaseCore(object):

    # some constants
    METARELEASE_URI = "http://changelogs.ubuntu.com/meta-release"
    METARELEASE_URI_UNSTABLE = "http://changelogs.ubuntu.com/meta-release-development"
    METARELEASE_URI_PROPOSED = "http://changelogs.ubuntu.com/meta-release-proposed"
    METARELEASE_FILE = "/var/lib/update-manager/meta-release"

    def __init__(self, useDevelopmentRelease=False, useProposed=False):
        # check what uri to use
        if useDevelopmentRelease:
            self.METARELEASE_URI = self.METARELEASE_URI_UNSTABLE
        elif useProposed:
            self.METARELEASE_URI = self.METARELEASE_URI_PROPOSED
        # check if we can access the METARELEASE_FILE
        if not os.access(self.METARELEASE_FILE, os.F_OK|os.W_OK|os.R_OK):
            path = os.path.expanduser("~/.update-manager/")
            if not os.path.exists(path):
                os.mkdir(path)
            self.METARELEASE_FILE = os.path.join(path,"meta-release")
        self.metarelease_information = None
        self.downloading = True
        # information about the available dists
        self.new_dist = None
        self.no_longer_supported = None
        # we start the download thread here and we have a timeout
        t=thread.start_new_thread(self.download, ())
        #t=thread.start_new_thread(self.check, ())

    def dist_no_longer_supported(self, dist):
        """ virtual function that is called when the distro is no longer
            supported
        """
        self.no_longer_supported = dist
    def new_dist_available(self, dist):
        """ virtual function that is called when a new distro release
            is available
        """
        self.new_dist = dist

    def get_dist(self):
        " return the codename of the current runing distro "
        p = Popen(["lsb_release","-c","-s"],stdout=PIPE)
        res = p.wait()
        if res != 0:
            sys.stderr.write("lsb_release returned exitcode: %i\n" % res)
        dist = string.strip(p.stdout.readline())
        return dist
    
    def parse(self):
        #print "parse"
        current_dist_name = self.get_dist()
        current_dist = None
        dists = []

        # parse the metarelease_information file
        index_tag = apt_pkg.ParseTagFile(self.metarelease_information)
        step_result = index_tag.Step()
        while step_result:
            if index_tag.Section.has_key("Dist"):
                name = index_tag.Section["Dist"]
                #print name
                rawdate = index_tag.Section["Date"]
                date = time.mktime(rfc822.parsedate(rawdate))
                supported = bool(index_tag.Section["Supported"])
                version = index_tag.Section["Version"]
                # add the information to a new date object
                dist = Dist(name, version, date,supported)
                if index_tag.Section.has_key("ReleaseNotes"):
                    dist.releaseNotesURI = index_tag.Section["ReleaseNotes"]
                if index_tag.Section.has_key("UpgradeTool"):
                    dist.upgradeTool =  index_tag.Section["UpgradeTool"]
                if index_tag.Section.has_key("UpgradeToolSignature"):
                    dist.upgradeToolSig =  index_tag.Section["UpgradeToolSignature"]
                dists.append(dist)
                if name == current_dist_name:
                    current_dist = dist 
            step_result = index_tag.Step()

        # first check if the current runing distro is in the meta-release
        # information. if not, we assume that we run on something not
        # supported and silently return
        if current_dist == None:
            print "current dist not found in meta-release file"
            return False

        # then see what we can upgrade to (only upgrade to supported dists)
        upgradable_to = ""
        for dist in dists:
            if dist.date > current_dist.date and dist.supported == True: 
                upgradable_to = dist
                #print "new dist: %s" % upgradable_to
                break

        # only warn if unsupported and a new dist is available (because 
        # the development version is also unsupported)
        if upgradable_to != "" and not current_dist.supported:
            self.dist_no_longer_supported(upgradabl_to)
        elif upgradable_to != "":
            self.new_dist_available(upgradable_to)

        # parsing done and sucessfully
        return True

    # the network thread that tries to fetch the meta-index file
    # can't touch the gui, runs as a thread
    def download(self):
        #print "download"
        lastmodified = 0
        req = urllib2.Request(self.METARELEASE_URI)
        if os.access(self.METARELEASE_FILE, os.W_OK):
            lastmodified = os.stat(self.METARELEASE_FILE).st_mtime
        if lastmodified > 0:
            req.add_header("If-Modified-Since", lastmodified)
        try:
            uri=urllib2.urlopen(req)
            if (os.path.exists(self.METARELEASE_FILE) and
                not os.access(self.METARELEASE_FILE,os.W_OK)):
                os.unlink(self.METARELEASE_FILE)
            f=open(self.METARELEASE_FILE,"w+")
            for line in uri.readlines():
                f.write(line)
            f.flush()
            f.seek(0,0)
            self.metarelease_information=f
            uri.close()
        except urllib2.URLError:
            if os.path.exists(self.METARELEASE_FILE):
                f=open(self.METARELEASE_FILE,"r")
        # now check the information we have
        self.downloading = False
        self.metarelease_information != None:
            self.parse()
