#!/usr/bin/python

import os
import os.path
import time

import sys
sys.path.insert(0, "../DistUpgrade")

from UpgradeTestBackend import UpgradeTestBackend
from UpgradeTestBackendQemu import *

import apt
import apt_pkg

if __name__ == "__main__":

    # create backend
    apt_pkg.Config.Set("APT::Architecture","i386")

    # FIXME: hardcoding pathes sucks
    basedir = "./profile/jaunty-auto-install"
    aptbasedir = os.path.join(basedir,"auto-install-test")
    profile = os.path.join(basedir, "DistUpgrade.cfg")
    backend = UpgradeTestBackendQemu(profile, profile)
    backend.bootstrap()

    # create dirs if needed
    for d in ["etc/apt/",
              "var/lib/dpkg",
              "var/lib/apt/lists/partial",
              "var/cache/apt/archives/partial"]:
        if not os.path.exists(os.path.join(aptbasedir,d)):
            os.makedirs(os.path.join(aptbasedir,d))

    # copy status file
    backend.start()
    print "copy status file"
    backend._copyFromImage("/var/lib/dpkg/status",
                           os.path.join(aptbasedir,"var/lib/dpkg/","status"))
    backend.stop()

    # build apt stuff (outside of the kvm)
    mirror = backend.config.get("NonInteractive","Mirror")
    dist = backend.config.get("Sources","From")
    components = backend.config.getlist("NonInteractive","Components")
    pockets =  backend.config.getlist("NonInteractive","Pockets")
    f=open(os.path.join(aptbasedir,"etc","apt","sources.list"),"w")
    f.write("deb %s %s %s\n" % (mirror, dist, " ".join(components)))
    for pocket in pockets:
        f.write("deb %s %s-%s %s\n" % (mirror, dist, pocket, " ".join(components)))
    f.close()
    
    # get a cache
    cache = apt.Cache(rootdir=os.path.abspath(aptbasedir))
    cache.update(apt.progress.TextFetchProgress())
    cache.open(apt.progress.OpProgress())

    # now test if we can install stuff
    backend.start()
    backend._runInImage(["apt-get","update"])

    resultdir = os.path.join(basedir,"result")
    statusfile = open(os.path.join(resultdir,"pkgs_done.txt"),"w")
    failures = open(os.path.join(resultdir,"failures.txt"),"w")
    # now see if we can install and remove it again
    for (i, pkg) in enumerate(cache):
        print "\n\nPackage %i of %i (%s)" % (i, len(cache), 
                                             float(i)/float(len(cache))*100)
        pkg_failed = False

        # skip stuff in the ubuntu-minimal that we can't install or upgrade
        if pkg.isInstalled and not pkg.isUpgradable:
            continue

        # see if we can install/upgrade the pkg
        try:
            pkg.markInstall()
        except SystemError, e:
            pkg.markKeep()
        if not (pkg.markedInstall or pkg.markedUpgrade):
            print "pkg: %s not installable" % pkg.name
            failures.write("%s markInstall()\n " % pkg.name)
            continue
        cache._depcache.Init()

        statusfile.write("%s\n" % pkg.name)
        # try to install it
        ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",pkg.name])
        print "apt returned: ", ret
        if ret != 0:
            print "apt returned a error"
            failures.write("%s install (%s)\n" % (pkg.name,ret))
            time.sleep(5)
            backend._copyFromImage("/var/log/apt/term.log",os.path.join(basedir,"result","%s-fail.txt" % pkg.name))
            pkg_failed = True
        # now remove it again
        ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","autoremove", "-y",pkg.name])
        print "apt returned: ", ret
        if ret != 0:
            failures.write("%s remove (%s)\n" % (pkg.name,ret))
            time.sleep(5)
            backend._copyFromImage("/var/log/apt/term.log",os.path.join(basedir,"result","%s-fail.txt" % pkg.name))
            pkg_failed = True
        statusfile.flush()
        failures.flush()
        if pkg_failed:
            # restart with a clean image
            self.stop()
            self.start()
    # all done, stop the backend
    backend.stop()

