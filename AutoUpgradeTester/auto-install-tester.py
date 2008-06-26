#!/usr/bin/python

import os
import os.path
import time

import sys
sys.path.insert(0, "../DistUpgrade")

from UpgradeTestBackend import UpgradeTestBackend
from UpgradeTestBackendQemu import *

import apt

if __name__ == "__main__":

    # create backend

    # FIXME: hardcoding pathes sucks
    basedir = "./profile/intrepid-auto-install"
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
    # write empty status file
    open(os.path.join(aptbasedir,"var/lib/dpkg/","status"),"w")

    # build apt stuff
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
    cache = apt.Cache(rootdir=aptbasedir) 
    cache.update()
    cache.open(apt.progress.OpProgress())

    # now test if we can install stuff
    backend.start()
    backend._runInImage(["apt-get","update"])
    backend.saveVMSnapshot("clean-base")

    # now see if we can install and remove it again
    for pkg in cache:
        ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",pkg.name])
        if ret != 0:
            backend.saveVMSnapshot("failed-install-%s" % pkg.name)
        ret = backend._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","autoremove", "-y",pkg.name])
        if ret != 0:
            backend.saveVMSnapshot("failed-autoremove-%s" % pkg.name)
        t = time.time()
        backend.restoreVMSnapshot("clean-base")
        print "restore took: %s" % (time.time()-t)
    
    # all done, stop the backend
    backend.stop()

