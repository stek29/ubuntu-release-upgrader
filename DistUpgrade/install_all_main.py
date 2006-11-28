#!/usr/bin/python

import apt
import apt_pkg

#apt_pkg.Config.Set("Dir::State::status","./empty")

cache = apt.Cache()
group = apt_pkg.GetPkgActionGroup(cache._depcache)
#print [pkg.name for pkg in cache if pkg.isInstalled]

troublemaker = set()
for pkg in cache:
    for c in pkg.candidateOrigin:
        if c.component == "main":
            current = set([p.name for p in cache if p.markedInstall])
            pkg.markInstall()
            new = set([p.name for p in cache if p.markedInstall])
            #if not pkg.markedInstall or len(new) < len(current):
            if not pkg.markedInstall:
                print "Can't install: %s" % pkg.name
            if len(current-new) > 0:
                troublemaker.add(pkg.name)
                print "Installing '%s' caused removals_ %s" % (pkg.name, current - new)

#print len(troublemaker)
for pkg in ["ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard"]:
    cache[pkg].markInstall()

print "We can install:"
print len([pkg.name for pkg in cache if pkg.markedInstall])
print "Download: "
pm = apt_pkg.GetPackageManager(cache._depcache)
fetcher = apt_pkg.GetAcquire()
pm.GetArchives(fetcher, cache._list, cache._records)
print apt_pkg.SizeToStr(fetcher.FetchNeeded)
print "Total space: ", apt_pkg.SizeToStr(cache._depcache.UsrSize)
cache.commit(apt.progress.FetchProgress(),apt.progress.InstallProgress())    
