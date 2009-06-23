#!/usr/bin/python

import os
import apt
import os.path
import string
import apt_pkg
import re
import logging

# global install blacklist
pkg_blacklist = None


class InstallProgress(apt.progress.InstallProgress):
   " Out install progress that can automatically remove broken pkgs "
   def error(self, pkg, errormsg):
      # on failure: 
      # - add failing package to "install_failures.txt"  [done]
      # - remove package from best.txt [done]
      # FIXME: - remove all rdepends from best.txt
      # - remove the failed install attempts [done]
      #   * explode if a package can not be removed and let the user cleanup
      open("install_failures.txt","a").write("%s _:_ %s" % (pkg, errormsg))
      bad = set()
      bad.add(os.path.basename(pkg).split("_")[0])
      # FIXME: just run apt-cache rdepends $pkg here?
      #        or use apt.Package.candidateDependencies ?
      #        or calculate the set again? <- BEST!
      for name in bad:
         new_best = open("best.txt").read().replace(name+"\n","")
         open("best.txt","w").write(new_best)
         open("install_blacklist.cfg","a").write("# auto added by install_all.py\n%s\n" % name)

def do_install(cache):
   # go and install
   res = False
   current = 0
   maxRetries = 5
   while current < maxRetries:
      print "Retry: ", current
      try:
         res = cache.commit(apt.progress.TextFetchProgress(),
                            InstallProgress())
         break
      except IOError, e:
         # fetch failed, will be retried
         current += 1
         print "Retrying to fetch: ", current, e
         continue
      except SystemError, e:
         print "Error installing packages! "
         print e
         print "Install result: ",res
         break
   # check for failed packages and remove them
   if os.path.exists("install_failures.txt"):
      failures =  set(map(lambda s: os.path.basename(s.split("_:_")[0]).split("_")[0], 
                          open("install_failures.txt").readlines()))
      print "failed: ", failures
      assert(os.system("dpkg -r %s" % " ".join(failures)) == 0)
      assert(os.system("dpkg --configure -a") == 0)
      # remove pos.txt and best.txt to force recalculation
      os.unlink("pos.txt")
      os.unlink("best.txt")
   return res

def blacklisted(name):
   global pkg_blacklist
   if pkg_blacklist is None and os.path.exists("install_blacklist.cfg"):
      pkg_blacklist = set()
      for name in map(string.strip, open("install_blacklist.cfg").readlines()):
         if name and not name.startswith("#"):
            pkg_blacklist.add(name)
      print "blacklist: ", pkg_blacklist
   if pkg_blacklist:
      for b in pkg_blacklist:
	   if re.match(b, name):
              return True
   return False

def clear(cache):
   cache._depcache.Init()

def reapply(cache, pkgnames):
   for name in pkgnames:
      cache[name].markInstall(False)

def contains_blacklisted_pkg(cache):
   for pkg in cache:
      if pkg.markedInstall and blacklisted(pkg.name):
         return True
   return False


# ----------------------------------------------------------------

#apt_pkg.Config.Set("Dir::State::status","./empty")

print "install_all.py"
os.environ["DEBIAN_FRONTEND"] = "noninteractive"
os.environ["APT_LISTCHANGES_FRONTEND"] = "none"

cache = apt.Cache()

# dapper does not have this yet 
try:
   group = apt_pkg.GetPkgActionGroup(cache._depcache)
except:
   pass
#print [pkg.name for pkg in cache if pkg.isInstalled]

# see what gives us problems
troublemaker = set()
best = set()

# first install all of main, then the rest
comps= ["main","universe"]
i=0

# reapply checkpoints
if os.path.exists("best.txt"):
   best = map(string.strip, open("best.txt").readlines())
   reapply(cache, best)

if os.path.exists("pos.txt"):
   (comp, i) = open("pos.txt").read().split()
   i = int(i)
   if comp == "universe":
      comps = ["universe"]

sorted_pkgs = cache.keys()[:]
sorted_pkgs.sort()


for comp in comps:
   for pkgname in sorted_pkgs[i:]:
      pkg = cache[pkgname]
      i += 1
      if pkg.candidateOrigin:
         print "\r%.3f" % (float(i)/(len(cache)*100.0)),
         for c in pkg.candidateOrigin:
            if comp == None or c.component == comp:
               current = set([p.name for p in cache if p.markedInstall])
               if not (pkg.isInstalled or blacklisted(pkg.name)):
                  try:
                     pkg.markInstall()
                  except SystemError, e:
                     print "Installing '%s' cause problems: %s" % (pkg.name, e)
                     pkg.markKeep()
                  # check blacklist
                  if contains_blacklisted_pkg(cache):
                     clear(cache)
                     reapply(cache, best)
                     continue
                  new = set([p.name for p in cache if p.markedInstall])
                  #if not pkg.markedInstall or len(new) < len(current):
                  if not (pkg.isInstalled or pkg.markedInstall):
                     print "Can't install: %s" % pkg.name
                  if len(current-new) > 0:
                     troublemaker.add(pkg.name)
                     print "Installing '%s' caused removals %s" % (pkg.name, current - new)
                  # FIXME: instead of len() use score() and score packages
                  #        according to criteria like "in main", "priority" etc
                  if len(new) >= len(best):
                     best = new
                     open("best.txt","w").write("\n".join(best))
                     open("pos.txt","w").write("%s %s" % (comp, i))
                  else:
                     print "Installing '%s' reduced the set (%s < %s)" % (pkg.name, len(new), len(best))
                     clear(cache)
                     reapply(cache, best)
   i=0

# make sure that the ubuntu base packages are installed
print len(troublemaker)
for pkg in ["ubuntu-desktop", "ubuntu-minimal", "ubuntu-standard"]:
    cache[pkg].markInstall()

# make sure we don't install blacklisted stuff
for pkg in cache:
	if blacklisted(pkg.name):
		pkg.markKeep()

# install it
print "We can install:"
print len([pkg.name for pkg in cache if pkg.markedInstall])
print "Download: "
pm = apt_pkg.GetPackageManager(cache._depcache)
fetcher = apt_pkg.GetAcquire()
pm.GetArchives(fetcher, cache._list, cache._records)
print apt_pkg.SizeToStr(fetcher.FetchNeeded)
print "Total space: ", apt_pkg.SizeToStr(cache._depcache.UsrSize)

# write out file with all pkgs
outf = "all_pkgs.cfg"
print "writing out file with the selected package names to '%s'" % outf
f = open(outf, "w")
f.write("\n".join([pkg.name for pkg in cache if pkg.markedInstall]))
f.close()

# now do the real install
res = do_install(cache)

if not res:
   # FIXME: re-exec itself
   sys.exit(1)

sys.exit(0)
