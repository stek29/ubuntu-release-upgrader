#!/usr/bin/python

import apt
import apt_pkg

def blacklisted(name):
	# we need to blacklist linux-image-* as it does not install
	# cleanly in the chroot (postinst failes)
	blacklist = ["linux-image-","ltsp-client"]
	for b in blacklist:
		if name.startswith(b):
			return True
	return False

#apt_pkg.Config.Set("Dir::State::status","./empty")

cache = apt.Cache()
group = apt_pkg.GetPkgActionGroup(cache._depcache)
#print [pkg.name for pkg in cache if pkg.isInstalled]

troublemaker = set()
for pkg in cache:
    for c in pkg.candidateOrigin:
        if c.component == "main":
            current = set([p.name for p in cache if p.markedInstall])
	    if not (pkg.isInstalled or blacklisted(pkg.name):
	            pkg.markInstall()
            new = set([p.name for p in cache if p.markedInstall])
            #if not pkg.markedInstall or len(new) < len(current):
	    if not (pkg.isInstalled or pkg.markedInstall):
                print "Can't install: %s" % pkg.name
            if len(current-new) > 0:
                troublemaker.add(pkg.name)
                print "Installing '%s' caused removals_ %s" % (pkg.name, current - new)

#print len(troublemaker)
for pkg in ["ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard"]:
    cache[pkg].markInstall()

# make sure we don't install blacklisted stuff
for pkg in cache:
	if blacklisted(pkg.name):
		pkg.markKeep()

print "We can install:"
print len([pkg.name for pkg in cache if pkg.markedInstall])
print "Download: "
pm = apt_pkg.GetPackageManager(cache._depcache)
fetcher = apt_pkg.GetAcquire()
pm.GetArchives(fetcher, cache._list, cache._records)
print apt_pkg.SizeToStr(fetcher.FetchNeeded)
print "Total space: ", apt_pkg.SizeToStr(cache._depcache.UsrSize)

res = False
current = 0
maxRetries = 3
while current < maxRetries:
    try:
        res = cache.commit(apt.progress.TextFetchProgress(),
                           apt.progress.InstallProgress())    
    except IOError, e:
        # fetch failed, will be retried
        current += 1
        print "Retrying to fetch: ", current
        continue
    except SystemError, e:
        print "Error installing packages! "
        print e
    print "Install result: ",res
    break
