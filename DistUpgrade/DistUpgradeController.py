# DistUpgradeController.py 
#  
#  Copyright (c) 2004-2006 Canonical
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


import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)
import apt
import apt_pkg
import sys
import os
import subprocess
import logging
import re
import statvfs
import shutil
import glob
import time
import copy
from stat import *
from string import Template

import DistUpgradeView
from DistUpgradeConfigParser import DistUpgradeConfig
from DistUpgradeFetcherCore import country_mirror

from sourceslist import SourcesList, SourceEntry, is_mirror
from distro import Distribution, get_distro, NoDistroTemplateException

from gettext import gettext as _
import gettext
from DistUpgradeCache import *
from DistUpgradeApport import *

# some constant
# the initrd space required in /boot for each kernel
KERNEL_INITRD_SIZE = 10*1024*1024

class NoBackportsFoundException(Exception):
    pass

class AptCdrom(object):
    def __init__(self, view, path):
        self.view = view
        self.cdrompath = path
        
    def restoreBackup(self, backup_ext):
        " restore the backup copy of the cdroms.list file (*not* sources.list)! "
        cdromstate = os.path.join(apt_pkg.Config.FindDir("Dir::State"),
                                  apt_pkg.Config.Find("Dir::State::cdroms"))
        if os.path.exists(cdromstate+backup_ext):
            shutil.copy(cdromstate+backup_ext, cdromstate)
        # mvo: we don't have to care about restoring the sources.list here because
        #      aptsources will do this for us anyway
        
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
        except SystemError, e:
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

class DistUpgradeController(object):
    """ this is the controller that does most of the work """
    
    def __init__(self, distUpgradeView, options=None, datadir=None):
        # setup the paths
        localedir = "/usr/share/locale/update-manager/"
        if datadir == None:
            datadir = os.getcwd()
            localedir = os.path.join(datadir,"mo")
            gladedir = datadir
        self.datadir = datadir
        self.options = options

        # init gettext
        gettext.bindtextdomain("update-manager",localedir)
        gettext.textdomain("update-manager")

        # setup the view
        logging.debug("Using '%s' view" % distUpgradeView.__class__.__name__)
        self._view = distUpgradeView
        self._view.updateStatus(_("Reading cache"))
        self.cache = None

        if not self.options or self.options.withNetwork == None:
            self.useNetwork = True
        else:
            self.useNetwork = self.options.withNetwork
        if options:
            cdrompath = options.cdromPath
        else:
            cdrompath = None
        self.aptcdrom = AptCdrom(distUpgradeView, cdrompath)

        # we act differently in server mode
        self.serverMode = False
        if self.options and self.options.mode == "server":
            self.serverMode = True
        # if we upgrade from a server CD we run in server mode
        if cdrompath:
            p = os.path.join(cdrompath, ".disk","info")
            if (os.path.exists(p) and 
                open(p).readline().startswith("Ubuntu-Server ")):
                self.serverMode = True
        
        # the configuration
        self.config = DistUpgradeConfig(datadir)
        self.sources_backup_ext = "."+self.config.get("Files","BackupExt")

        # move some of the options stuff into the self.config, 
        # ConfigParser deals only with strings it seems *sigh*
        self.config.add_section("Options")
        self.config.set("Options","withNetwork", str(self.useNetwork))
        
        # some constants here
        self.fromDist = self.config.get("Sources","From")
        self.toDist = self.config.get("Sources","To")
        self.origin = self.config.get("Sources","ValidOrigin")
        self.arch = apt_pkg.Config.Find("APT::Architecture")

        # we run with --force-overwrite by default
        if not os.environ.has_key("RELEASE_UPGRADE_NO_FORCE_OVERWRITE"):
            logging.debug("enable dpkg --force-overwrite")
            apt_pkg.Config.Set("DPkg::Options::","--force-overwrite")

        # we run in full upgrade mode by default
        self.partialUpgrade = False

        # setup env var 
        os.environ["RELEASE_UPGRADE_IN_PROGRESS"] = "1"
        if self.serverMode:
            os.environ["RELEASE_UPGRADE_MODE"] = "server"
        else:
            os.environ["RELEASE_UPGRADE_MODE"] = "desktop"
        os.environ["PYCENTRAL_NO_DPKG_QUERY"] = "1"
        os.environ["PATH"] = "%s:%s" % (os.getcwd()+"/imported",
                                        os.environ["PATH"])

        # set max retries
        maxRetries = self.config.getint("Network","MaxRetries")
        apt_pkg.Config.Set("Acquire::Retries", str(maxRetries))
        # max sizes for dpkgpm for large installs (see linux/limits.h and 
        #                                          linux/binfmts.h)
        apt_pkg.Config.Set("Dpkg::MaxArgs", str(64*1024))
        apt_pkg.Config.Set("Dpkg::MaxArgBytes", str(128*1024))

        # smaller to avoid hangs
        apt_pkg.Config.Set("Acquire::http::Timeout","20")
        apt_pkg.Config.Set("Acquire::ftp::Timeout","20")

        # forced obsoletes
        self.forced_obsoletes = self.config.getlist("Distro","ForcedObsoletes")
        # list of valid mirrors that we can add
        self.valid_mirrors = self.config.getListFromFile("Sources","ValidMirrors")

    def openCache(self, lock=True):
        if self.cache is not None:
            self.cache.releaseLock()
            self.cache.unlockListsDir()
        try:
            self.cache = MyCache(self.config,
                                 self._view,
                                 self._view.getOpCacheProgress(),
                                 lock)
        # if we get a dpkg error that it was interrupted, just
        # run dpkg --configure -a
        except CacheExceptionDpkgInterrupted, e:
            logging.warning("dpkg interrupted, calling dpkg --configure -a")
            self._view.getTerminal().call(["dpkg","--configure","-a"])
            self.cache = MyCache(self.config,
                                 self._view,
                                 self._view.getOpCacheProgress())
        except CacheExceptionLockingFailed, e:
            logging.error("Cache can not be locked (%s)" % e)
            self._view.error(_("Unable to get exclusive lock"),
                             _("This usually means that another "
                               "package management application "
                               "(like apt-get or aptitude) "
                               "already running. Please close that "
                               "application first."));
            sys.exit(1)

    def _sshMagic(self):
        """ this will check for server mode and if we run over ssh.
            if this is the case, we will ask and spawn a additional
            daemon (to be sure we have a spare one around in case
            of trouble)
        """
        pidfile = os.path.join("/var/run/release-upgrader-sshd.pid")
        if (not os.path.exists(pidfile) and
            (os.environ.has_key("SSH_CONNECTION") or
             os.environ.has_key("SSH_TTY"))):
            port = 9004
            res = self._view.askYesNoQuestion(
                _("Continue running under SSH?"),
                _("This session appears to be running under ssh. "
                  "It is not recommended to perform a upgrade "
                  "over ssh currently because in case of failure "
                "it is harder to recover.\n\n"
                  "If you continue, a additional ssh daemon will be "
                  "started at port '%s'.\n"
                  "Do you want to continue?") % port)
            # abort
            if res == False:
                sys.exit(1)
            res = subprocess.call(["/usr/sbin/sshd",
                                   "-o", "PidFile=%s" % pidfile,
                                   "-p",str(port)])
            if res == 0:
                self._view.information(
                    _("Starting additional sshd"),
                    _("To make recovery in case of failure easier, an "
                      "additional sshd will be started on port '%s'. "
                      "If anything goes wrong with the running ssh "
                      "you can still connect to the additional one.\n"
                      ) % port)

    def _tryUpdateSelf(self):
        """ this is a helper that is run if we are started from a CD
            and we have network - we will then try to fetch a update
            of ourself
        """  
        from MetaRelease import MetaReleaseCore
        from DistUpgradeFetcherSelf import DistUpgradeFetcherSelf
        # check if we run from a LTS 
        forceLTS=False
        if (self.release == "dapper" or
            self.release == "hardy"):
            forceLTS=True
        m = MetaReleaseCore(useDevelopmentRelease=False,
                            forceLTS=forceLTS)
        # this will timeout eventually
        while m.downloading:
            self._view.processEvents()
            time.sleep(0.1)
        if m.new_dist is None:
            logging.error("No new dist found")
            return False
        # we have a new dist
        progress = self._view.getFetchProgress()
        fetcher = DistUpgradeFetcherSelf(new_dist=m.new_dist,
                                         progress=progress,
                                         options=self.options,
                                         view=self._view)
        fetcher.run()

    def _pythonSymlinkCheck(self):
        """ sanity check that /usr/bin/python points to the default
            python version. Users tend to modify this symlink, which
            breaks stuff in obscure ways (Ubuntu #75557).
        """
        logging.debug("_pythonSymlinkCheck run")
        from ConfigParser import SafeConfigParser, NoOptionError
        if os.path.exists('/usr/share/python/debian_defaults'):
            config = SafeConfigParser()
            config.readfp(file('/usr/share/python/debian_defaults'))
            try:
                expected_default = config.get('DEFAULT', 'default-version')
            except NoOptionError:
                logging.debug("no default version for python found in '%s'" % config)
                return False
            try:
                fs_default_version = os.readlink('/usr/bin/python')
            except OSError, e:
                logging.error("os.readlink failed (%s)" % e)
                return False
            if not fs_default_version in (expected_default, os.path.join('/usr/bin', expected_default)):
                logging.debug("python symlink points to: '%s', but expected is '%s' or '%s'" % (fs_default_version, expected_default, os.path.join('/usr/bin', expected_default)))
                return False
        return True
    
    def prepare(self):
        """ initial cache opening, sanity checking, network checking """
        # first check if that is a good upgrade
        self.release = release = subprocess.Popen(["lsb_release","-c","-s"],
                                   stdout=subprocess.PIPE).communicate()[0].strip()
        logging.debug("lsb-release: '%s'" % release)
        if not (release == self.fromDist or release == self.toDist):
            logging.error("Bad upgrade: '%s' != '%s' " % (release, self.fromDist))
            self._view.error(_("Can not upgrade"),
                             _("A upgrade from '%s' to '%s' is not "
                               "supported with this tool." % (release, self.toDist)))
            sys.exit(1)
        # setup backports (if we have them)
        if self.options and self.options.havePrerequists:
            backportsdir = os.getcwd()+"/backports"
            logging.info("using backports in '%s' " % backportsdir)
            logging.debug("have: %s" % glob.glob(backportsdir+"/*.udeb"))
            if os.path.exists(backportsdir+"/usr/bin/dpkg"):
                apt_pkg.Config.Set("Dir::Bin::dpkg",backportsdir+"/usr/bin/dpkg");
            if os.path.exists(backportsdir+"/usr/lib/apt/methods"):
                apt_pkg.Config.Set("Dir::Bin::methods",backportsdir+"/usr/lib/apt/methods")
            conf = backportsdir+"/etc/apt/apt.conf.d/01ubuntu"
            if os.path.exists(conf):
                logging.debug("adding config '%s'" % conf)
                apt_pkg.ReadConfigFile(apt_pkg.Config, conf)

        # do the ssh check and warn if we run under ssh
        self._sshMagic()
        # check python version
        if not self._pythonSymlinkCheck():
            logging.error("pythonSymlinkCheck() failed, aborting")
            self._view.error(_("Can not upgrade"),
                             _("Your python install is corrupted. "
                               "Please fix the '/usr/bin/python' symlink."))
            sys.exit(1)
        # open cache
        try:
            self.openCache()
        except SystemError, e:
            logging.error("openCache() failed: '%s'" % e)
            return False
        if not self.cache.sanityCheck(self._view):
            return False

        if not self.checkViewDepends():
            logging.error("checkViewDepends() failed")
            return False

        if os.path.exists("/usr/bin/debsig-verify"):
            logging.error("debsig-verify is installed")
            self._view.error(_("Package 'debsig-verify' is installed"),
                             _("The upgrade can not continue with that "
                               "package installed.\n"
                               "Please remove it with synaptic "
                               "or 'apt-get remove debsig-verify' first "
                               "and run the upgrade again."))
            self.abort()

        # FIXME: we may try to find out a bit more about the network
        # connection here and ask more  intelligent questions
        if self.aptcdrom and self.options and self.options.withNetwork == None:
            res = self._view.askYesNoQuestion(_("Include latest updates from the Internet?"),
                                              _("The upgrade process can automatically download "
                                                "the latest updates and install them during the "
                                                "upgrade.  The upgrade will take longer, but when "
                                                "it is complete, your system will be fully up to "
                                                "date.  You can choose not to do this, but you "
                                                "should install the latest updates soon after "
                                                "upgrading."),
                                              'Yes'
                                              )
            self.useNetwork = res
            logging.debug("useNetwork: '%s' (selected by user)" % res)
            if res:
                self._tryUpdateSelf()
        return True

    def rewriteSourcesList(self, mirror_check=True):
        logging.debug("rewriteSourcesList()")

        # check if we need to enable main
        if mirror_check == True and self.useNetwork:
            # now check if the base-meta pkgs are available in
            # the archive or only available as "now"
            # -> if not that means that "main" is missing and we
            #    need to  enable it
            for pkgname in self.config.getlist("Distro","BaseMetaPkgs"):
                if ((not self.cache.has_key(pkgname)
                     or
                     len(self.cache[pkgname].candidateOrigin) == 0)
                    or
                    (len(self.cache[pkgname].candidateOrigin) == 1 and
                     self.cache[pkgname].candidateOrigin[0].archive == "now")
                   ):
                    logging.debug("BaseMetaPkg '%s' has no candidateOrigin" % pkgname)
                    try:
                        distro = get_distro()
                        distro.get_sources(self.sources)
                        distro.enable_component("main")
                    except NoDistroTemplateException,e :
                        # fallback if everything else does not work,
                        # we replace the sources.list with a single
                        # line to ubuntu-main
                        logging.warning('get_distro().enable_component("man") failed, overwriting sources.list instead as last resort')
                        s = "deb http://archive.ubuntu.com/ubuntu %s main" % self.toDist
                        open("/etc/apt/sources.list","w").write(s)
                    break
            
        # this must map, i.e. second in "from" must be the second in "to"
        # (but they can be different, so in theory we could exchange
        #  component names here)
        fromDists = [self.fromDist,
                     self.fromDist+"-security",
                     self.fromDist+"-updates",
                     self.fromDist+"-proposed",
                     self.fromDist+"-backports"
                    ]
        toDists = [self.toDist,
                   self.toDist+"-security",
                   self.toDist+"-updates",
                   self.toDist+"-proposed",
                   self.toDist+"-backports"
                   ]

        self.sources_disabled = False

        # look over the stuff we have
        foundToDist = False
        for entry in self.sources.list[:]:

            # ignore invalid records or disabled ones
            if entry.invalid or entry.disabled:
                continue
            
            # we disable breezy cdrom sources to make sure that demoted
            # packages are removed
            if entry.uri.startswith("cdrom:") and entry.dist == self.fromDist:
                entry.disabled = True
                continue
            # ignore cdrom sources otherwise
            elif entry.uri.startswith("cdrom:"):
                continue

            # special case for archive.canonical.com that needs to
            # be rewritten (for pre-gutsy upgrades)
            cdist = "%s-commercial" % self.fromDist
            if (not entry.disabled and
                entry.uri.startswith("http://archive.canonical.com") and
                entry.dist == cdist):
                entry.dist = self.toDist
                entry.comps = ["partner"]
                logging.debug("transitioned commercial to '%s' " % entry)
                continue

            # special case for landscape.canonical.com because they
            # don't use a standard archive layout
            if (not entry.disabled and
                entry.uri.startswith("http://landscape.canonical.com/packages/%s" % self.fromDist)):
                entry.uri = "http://landscape.canonical.com/packages/%s" % self.toDist
                logging.debug("transitioning landscape.canonical.com to '%s' " % entry)
                continue
                

            logging.debug("examining: '%s'" % entry)
            # check if it's a mirror (or official site)
            validMirror = self.isMirror(entry.uri)
            if validMirror or not mirror_check:
                validMirror = True
                # disabled/security/commercial are special cases
                # we use validTo/foundToDist to figure out if we have a 
                # main archive mirror in the sources.list or if we 
                # need to add one
                validTo = True
                if (entry.disabled or
                    entry.uri.startswith("http://security.ubuntu.com") or
                    entry.uri.startswith("http://archive.canonical.com")):
                    validTo = False
                if entry.dist in toDists:
                    # so the self.sources.list is already set to the new
                    # distro
                    logging.debug("entry '%s' is already set to new dist" % entry)
                    foundToDist |= validTo
                elif entry.dist in fromDists:
                    foundToDist |= validTo
                    entry.dist = toDists[fromDists.index(entry.dist)]
                    logging.debug("entry '%s' updated to new dist" % entry)
                else:
                    # disable all entries that are official but don't
                    # point to either "to" or "from" dist
                    entry.disabled = True
                    self.sources_disabled = True
                    logging.debug("entry '%s' was disabled (unknown dist)" % entry)
                
                # if we make it to this point, we have a official mirror
                # 
                # check if the arch is powerpc or sparc and if so, transition
                # to ports.ubuntu.com (powerpc got demoted in gutsy, sparc
                # in hardy)
                    
                if (entry.type == "deb" and
                    not "ports.ubuntu.com" in entry.uri and
                    (self.arch == "powerpc" or self.arch == "sparc")):
                    logging.debug("moving %s source entry to 'ports.ubuntu.com' " % self.arch)
                    entry.uri = "http://ports.ubuntu.com/ubuntu-ports/"
                    

            # disable anything that is not from a official mirror
            if not validMirror:
                entry.disabled = True
                self.sources_disabled = True
                logging.debug("entry '%s' was disabled (unknown mirror)" % entry)
        return foundToDist

    def updateSourcesList(self):
        logging.debug("updateSourcesList()")
        self.sources = SourcesList(matcherPath=".")
        if not self.rewriteSourcesList(mirror_check=True):
            logging.error("No valid mirror found")
            res = self._view.askYesNoQuestion(_("No valid mirror found"),
                             _("While scanning your repository "
                               "information no mirror entry for "
                               "the upgrade was found."
                               "This can happen if you run a internal "
                               "mirror or if the mirror information is "
                               "out of date.\n\n"
                               "Do you want to rewrite your "
                               "'sources.list' file anyway? If you choose "
                               "'Yes' here it will update all '%s' to '%s' "
                               "entries.\n"
                               "If you select 'no' the update will cancel."
                               ) % (self.fromDist, self.toDist))
            if res:
                # re-init the sources and try again
                self.sources = SourcesList(matcherPath=".")
                # its ok if rewriteSourcesList fails here if
                # we do not use a network, the sources.list may be empty
                if (not self.rewriteSourcesList(mirror_check=False)
                    and self.useNetwork):
                    #hm, still nothing useful ...
                    prim = _("Generate default sources?")
                    secon = _("After scanning your 'sources.list' no "
                              "valid entry for '%s' was found.\n\n"
                              "Should default entries for '%s' be "
                              "added? If you select 'No', the update "
                              "will cancel.") % (self.fromDist, self.toDist)
                    if not self._view.askYesNoQuestion(prim, secon):
                        self.abort()

                    # add some defaults here
                    # FIXME: find mirror here
                    uri = "http://archive.ubuntu.com/ubuntu"
                    comps = ["main","restricted"]
                    self.sources.add("deb", uri, self.toDist, comps)
                    self.sources.add("deb", uri, self.toDist+"-updates", comps)
                    self.sources.add("deb",
                                     "http://security.ubuntu.com/ubuntu/",
                                     self.toDist+"-security", comps)
            else:
                self.abort()

        # write (well, backup first ;) !
        self.sources.backup(self.sources_backup_ext)
        self.sources.save()

        # re-check if the written self.sources are valid, if not revert and
        # bail out
        # TODO: check if some main packages are still available or if we
        #       accidentally shot them, if not, maybe offer to write a standard
        #       sources.list?
        try:
            sourceslist = apt_pkg.GetPkgSourceList()
            sourceslist.ReadMainList()
        except SystemError:
            logging.error("Repository information invalid after updating (we broke it!)")
            self._view.error(_("Repository information invalid"),
                             _("Upgrading the repository information "
                               "resulted in a invalid file. Please "
                               "report this as a bug."))
            return False

        if self.sources_disabled:
            self._view.information(_("Third party sources disabled"),
                             _("Some third party entries in your sources.list "
                               "were disabled. You can re-enable them "
                               "after the upgrade with the "
                               "'software-properties' tool or "
                               "your package manager."
                               ))
        return True

    def _logChanges(self):
        # debugging output
        logging.debug("About to apply the following changes")
        inst = []
        up = []
        rm = []
        held = []
        for pkg in self.cache:
            if pkg.markedInstall: inst.append(pkg.name)
            elif pkg.markedUpgrade: up.append(pkg.name)
            elif pkg.markedDelete: rm.append(pkg.name)
            elif (pkg.isInstalled and pkg.isUpgradable): held.append(pkg.name)
        logging.debug("Held-back: %s" % " ".join(held))
        logging.debug("Remove: %s" % " ".join(rm))
        logging.debug("Install: %s" % " ".join(inst))
        logging.debug("Upgrade: %s" % " ".join(up))
        

    def doPreUpgrade(self):
        # check if we have packages in ReqReinst state that are not
        # downloadable
        logging.debug("doPreUpgrade")
        if len(self.cache.reqReinstallPkgs) > 0:
            logging.warning("packages in reqReinstall state, trying to fix")
            self.cache.fixReqReinst(self._view)
            self.openCache()
        if len(self.cache.reqReinstallPkgs) > 0:
            reqreinst = self.cache.reqReinstallPkgs
            header = gettext.ngettext("Package in inconsistent state",
                                      "Packages in inconsistent state",
                                      len(reqreinst))
            summary = gettext.ngettext("The package '%s' is in a inconsistent "
                                       "state and needs to be reinstalled, but "
                                       "no archive can be found for it. "
                                       "Please reinstall the package manually "
                                       "or remove it from the system.",
                                       "The packages '%s' is in a inconsistent "
                                       "state and needs to be reinstalled, but "
                                       "no archive can be found for it."
                                       "Please reinstall the packages manually "
                                       "or remove them from the system.",
                                       len(reqreinst)) % ", ".join(reqreinst)
            self._view.error(header, summary)
            return False
        # FIXME: check out what packages are downloadable etc to
        # compare the list after the update again
        self.obsolete_pkgs = self.cache._getObsoletesPkgs()
        self.foreign_pkgs = self.cache._getForeignPkgs(self.origin, self.fromDist, self.toDist)
        if self.serverMode:
            self.tasks = self.cache.installedTasks
        logging.debug("Foreign: %s" % " ".join(self.foreign_pkgs))
        logging.debug("Obsolete: %s" % " ".join(self.obsolete_pkgs))
        return True

    def doUpdate(self, showErrors=True, forceRetries=None):
        logging.debug("running doUpdate() (showErrors=%s)" % showErrors)
        if not self.useNetwork:
            logging.debug("doUpdate() will not use the network because self.useNetwork==false")
            return True
        self.cache._list.ReadMainList()
        progress = self._view.getFetchProgress()
        # FIXME: also remove all files from the lists partial dir!
        currentRetry = 0
        if forceRetries is not None:
            maxRetries=forceRetries
        else:
            maxRetries = self.config.getint("Network","MaxRetries")
        while currentRetry < maxRetries:
            try:
                res = self.cache.update(progress)
            except (SystemError, IOError), e:
                logging.error("IOError/SystemError in cache.update(): '%s'. Retrying (currentRetry: %s)" % (e,currentRetry))
                currentRetry += 1
                continue
            # no exception, so all was fine, we are done
            return True

        logging.error("doUpdate() failed completely")
        if showErrors:
            self._view.error(_("Error during update"),
                             _("A problem occurred during the update. "
                               "This is usually some sort of network "
                               "problem, please check your network "
                               "connection and retry."), "%s" % e)
        return False


    def _checkFreeSpace(self):
        " this checks if we have enough free space on /var and /usr"
        err_sum = _("Not enough free disk space")
        err_long= _("The upgrade aborts now. "
                    "The upgrade needs a total of %s free space on disk '%s'. "
                    "Please free at least an additional %s of disk "
                    "space on '%s'. "
                    "Empty your trash and remove temporary "
                    "packages of former installations using "
                    "'sudo apt-get clean'.")

        class FreeSpace(object):
            " helper class that represents the free space on each mounted fs "
            def __init__(self, initialFree):
                self.free = initialFree
                self.need = 0

        def make_fs_id(d):
            """ return 'id' of a directory so that directories on the
                same filesystem get the same id (simply the mount_point)
            """
            for mount_point in mounted:
                if d.startswith(mount_point):
                    return mount_point
            return "/"

        # this is all a bit complicated
        # 1) check what is mounted (in mounted)
        # 2) create FreeSpace objects for the dirs we are interested in
        #    (mnt_map)
        # 3) use the  mnt_map to check if we have enough free space and
        #    if not tell the user how much is missing
        mounted = []
        mnt_map = {}
        fs_free = {}
        for line in open("/proc/mounts"):
            try:
                (what, where, fs, options, a, b) = line.split()
            except ValueError, e:
                logging.debug("line '%s' in /proc/mounts not understood (%s)" % (line, e))
                continue
            if not where in mounted:
                mounted.append(where)
        # make sure mounted is sorted by longest path
        mounted.sort(cmp=lambda a,b: cmp(len(a),len(b)), reverse=True)
        archivedir = apt_pkg.Config.FindDir("Dir::Cache::archives")
        for d in ["/","/usr","/var","/boot", archivedir, "/home"]:
            d = os.path.realpath(d)
            fs_id = make_fs_id(d)
            st = os.statvfs(d)
            free = st[statvfs.F_BAVAIL]*st[statvfs.F_FRSIZE]
            if fs_id in mnt_map:
                logging.debug("Dir %s mounted on %s" % (d,mnt_map[fs_id]))
                fs_free[d] = fs_free[mnt_map[fs_id]]
            else:
                logging.debug("Free space on %s: %s" % (d,free))
                mnt_map[fs_id] = d
                fs_free[d] = FreeSpace(free)
        del mnt_map
        logging.debug("fs_free contains: '%s'" % fs_free)

        # now calculate the space that is required on /boot
        # we do this by checking how many linux-image-$ver packages
        # are installed or going to be installed
        space_in_boot = 0
        for pkg in self.cache:
            # we match against everything that looks like a kernel
            # and add space check to filter out metapackages
            if re.match("^linux-(image|image-debug)-[0-9.]*-.*", pkg.name):
                if pkg.markedInstall:
                    logging.debug("%s (new-install) added with %s to boot space" % (pkg.name, KERNEL_INITRD_SIZE))
                    space_in_boot += KERNEL_INITRD_SIZE
                elif (pkg.markedUpgrade or pkg.isInstalled):
                    logging.debug("%s (upgrade|installed) added with %s to boot space" % (pkg.name, KERNEL_INITRD_SIZE))
                    space_in_boot += KERNEL_INITRD_SIZE # creates .bak

        # we check for various sizes:
        # archivedir is were we download the debs
        # /usr is assumed to get *all* of the install space (incorrect,
        #      but as good as we can do currently + safety buffer
        # /     has a small safety buffer as well
        for (dir, size) in [(archivedir, self.cache.requiredDownload),
                            ("/usr", self.cache.additionalRequiredSpace),
                            ("/usr", 50*1024*1024),  # safety buffer /usr
                            ("/boot", space_in_boot), 
                            ("/", 10*1024*1024),     # small safety buffer /
                           ]:
            dir = os.path.realpath(dir)
            logging.debug("dir '%s' needs '%s' of '%s' (%f)" % (dir, size, fs_free[dir], fs_free[dir].free))
            fs_free[dir].free -= size
            fs_free[dir].need += size
            if fs_free[dir].free < 0:
                free_at_least = apt_pkg.SizeToStr(float(abs(fs_free[dir].free)+1))
                logging.error("not enough free space on %s (missing %s)" % (dir, free_at_least))
                self._view.error(err_sum, err_long % (apt_pkg.SizeToStr(fs_free[dir].need), make_fs_id(dir), free_at_least, make_fs_id(dir)))
                return False

            
        return True


    def askDistUpgrade(self):
        # check what packages got demoted and ask the user
        # if those shall be removed
        demotions = set()
        demotions_file = self.config.get("Distro","Demotions")
        if os.path.exists(demotions_file):
            map(lambda pkgname: demotions.add(pkgname.strip()),
                filter(lambda line: not line.startswith("#"),
                       open(demotions_file).readlines()))
        self.installed_demotions = [pkg.name for pkg in self.cache if pkg.isInstalled and pkg.name in demotions]
        if len(self.installed_demotions) > 0:
	    self.installed_demotions.sort()
            logging.debug("demoted: '%s'" % " ".join(self.installed_demotions))
            self._view.showDemotions(_("Support for some applications ended"),
                                   _("Canonical Ltd. no longer provides "
                                     "support for the following software "
                                     "packages. You can still get support "
                                     "from the community.\n\n"
                                     "If you have not enabled community "
                                     "maintained software (universe), "
                                     "these packages will be suggested for "
                                     "removal at the end of the upgrade."),
                                     self.installed_demotions)
            self._view.updateStatus(_("Calculating the changes"))
        # FIXME: integrate this into main upgrade dialog!?!
        if not self.cache.distUpgrade(self._view, self.serverMode, self.partialUpgrade):
            return False

        if self.serverMode:
            if not self.cache.installTasks(self.tasks):
                return False
        changes = self.cache.getChanges()
        # log the changes for debugging
        self._logChanges()
        # check if we have enough free space 
        if not self._checkFreeSpace():
            return False
        # ask the user if he wants to do the changes
        res = self._view.confirmChanges(_("Do you want to start the upgrade?"),
                                        changes,
                                        self.cache.requiredDownload)
        return res

    def _rewriteAptPeriodic(self, minAge, makeBackup=False):
        # rewrite apt minage cleanup to avoid 
        for name in ["/etc/apt/apt.conf.d/20archive",
                     "/etc/apt/apt.conf.d/25adept-archive-limits"]:
            if not os.path.exists(name):
                logging.debug("no file '%s'" % name)
                break
            try:
                outname = "%s.distUpgrade" % name
                out = open(outname, "w")
                for line in open(name):
                    if line.startswith("APT::Archives::MinAge"):
                        logging.debug("setting MinAge to %s" % minAge)
                        line = 'APT::Archives::MinAge "%s";\n' % minAge
                    out.write(line)
                if makeBackup:
                    shutil.copy(name, name+".save")
                out.close()
                os.rename(outname, name)
            except Exception, e:
                logging.waring("failed to modify '%s' (%s)" % (name, e))

    def doDistUpgradeFetching(self):
        # rewrite cleanup minAge for a package to 10 days
        self.apt_minAge = apt_pkg.Config.FindI("APT::Archives::MinAge")
        self._rewriteAptPeriodic(10)
        # get the upgrade
        currentRetry = 0
        fprogress = self._view.getFetchProgress()
        iprogress = self._view.getInstallProgress(self.cache)
        # retry the fetching in case of errors
        maxRetries = self.config.getint("Network","MaxRetries")
        # FIXME: we get errors like 
        #   "I wasn't able to locate file for the %s package" 
        #  here sometimes. its unclear why and not reproducible, the 
        #  current theory is that for some reason the file is not
        #  considered trusted at the moment 
        #  pkgAcquireArchive::QueueNext() runs debReleaseIndex::IsTrused()
        #  (the later just checks for the existence of the .gpg file)
        #  OR 
        #  the fact that we get a pm and fetcher here confuses something
        #  in libapt?
        # POSSIBLE workaround: keep the list-dir locked so that 
        #          no apt-get update can run outside from the release
        #          upgrader 
        while currentRetry < maxRetries:
            try:
                pm = apt_pkg.GetPackageManager(self.cache._depcache)
                fetcher = apt_pkg.GetAcquire(fprogress)
                res = self.cache._fetchArchives(fetcher, pm)
            except IOError, e:
                # fetch failed, will be retried
                logging.error("IOError in cache.commit(): '%s'. Retrying (currentTry: %s)" % (e,currentRetry))
                currentRetry += 1
                continue
            return True
        
        # maximum fetch-retries reached without a successful commit
        logging.error("giving up on fetching after maximum retries")
        self._view.error(_("Could not download the upgrades"),
                         _("The upgrade aborts now. Please check your "\
                           "Internet connection or "\
                           "installation media and try again. "),
                           "%s" % e)
        # abort here because we want our sources.list back
        self.abort()
        
    
    def doDistUpgrade(self):
        # get the upgrade
        currentRetry = 0
        fprogress = self._view.getFetchProgress()
        iprogress = self._view.getInstallProgress(self.cache)
        # retry the fetching in case of errors
        maxRetries = self.config.getint("Network","MaxRetries")
        while currentRetry < maxRetries:
            try:
                res = self.cache.commit(fprogress,iprogress)
            except SystemError, e:
                logging.error("SystemError from cache.commit(): %s" % e)
                # check if the installprogress catched a pkgfailure, 
                # if not, generate a fallback here
                if iprogress.pkg_failures == 0:
                    logging.warning("cache.commit() raised a SystemError but pkg_failures count is 0")
                    errormsg = "SystemError in cache.commit(): %s" % e
                    apport_pkgfailure("update-manager", errormsg)
                # invoke the frontend now
                msg = _("The upgrade aborts now. Your system "
                        "could be in an unusable state. A recovery "
                        "will run now (dpkg --configure -a).")
                if not self.partialUpgrade:
                    if not run_apport():
                        msg += _("\n\nPlease report this bug against the 'update-manager' "
                                 "package and include the files in /var/log/dist-upgrade/ "
                                 "in the bugreport.\n"
                                 "%s" % e)
                self._view.error(_("Could not install the upgrades"), msg)
                # installing the packages failed, can't be retried
                self._view.getTerminal().call(["dpkg","--configure","-a"])
                self._rewriteAptPeriodic(self.apt_minAge)
                self._fixupEnvy()
                return False
            except IOError, e:
                # fetch failed, will be retried
                logging.error("IOError in cache.commit(): '%s'. Retrying (currentTry: %s)" % (e,currentRetry))
                currentRetry += 1
                continue
            # no exception, so all was fine, we are done
            self._rewriteAptPeriodic(self.apt_minAge)
            return True
        
        # maximum fetch-retries reached without a successful commit
        logging.error("giving up on fetching after maximum retries")
        self._view.error(_("Could not download the upgrades"),
                         _("The upgrade aborts now. Please check your "\
                           "Internet connection or "\
                           "installation media and try again. "),
                           "%s" % e)
        # abort here because we want our sources.list back
        self.abort()

    def _fixupEnvy(self):
        " fixupEnvy "
        if (os.path.exists("/var/log/envy-installer.log") and
            os.path.getsize("/var/log/envy-installer.log") > 0):
            logging.warning("envy detected, fixing configuration")
            # fixup /etc/default/linux-restricted-modules-common
            # and comment DISABLED_MODULES
            lrm_path = "/etc/default/linux-restricted-modules-common"
            if os.path.exists(lrm_path):
                lrm = open(lrm_path).read()
                f = open(lrm_path,"w")
                for line in lrm.split("\n"):
                    if line.startswith("DISABLED_MODULES="):
                        logging.warning("editing DISABLED_MODULES")
                        line = line.replace("nvidia_legacy","")
                        line = line.replace("nvidia_new","")
                        line = line.replace("nvidia","")
                        line = line.replace("nv","")
                        line = line.replace("fglrx","")
                    f.write(line+"\n")
            # now uncomment /etc/modprobe.d/lrm-video
            lrm_video = "/etc/modprobe.d/lrm-video"
            if os.path.exists(lrm_video):
                lrm = open(lrm_video).read()
                f = open(lrm_video,"w")
                for line in lrm.split("\n"):
                    if line.startswith("#install"):
                        line = line[1:]
                    f.write(line+"\n")
        return True

    def doPostUpgrade(self):
        # reopen cache
        self.openCache()
        
        # now run the quirksHandler 
        for name in ("%sQuirks", "from_%sQuirks"):
            quirksFuncName = name % self.config.get("Sources","From")
            func = getattr(self, quirksFuncName, None)
            if func is not None:
                func()

        # fixup envy
        self._fixupEnvy()

        # check out what packages are cruft now
        # use self.{foreign,obsolete}_pkgs here and see what changed
        now_obsolete = self.cache._getObsoletesPkgs()
        now_foreign = self.cache._getForeignPkgs(self.origin, self.fromDist, self.toDist)
        logging.debug("Obsolete: %s" % " ".join(now_obsolete))
        logging.debug("Foreign: %s" % " ".join(now_foreign))
        # check if we actually want obsolete removal
        if not self.config.getWithDefault("Distro","RemoveObsoletes", True):
            logging.debug("Skipping obsolete Removal")
            return True

        # now get the meta-pkg specific obsoletes and purges
        for pkg in self.config.getlist("Distro","MetaPkgs"):
            if self.cache.has_key(pkg) and self.cache[pkg].isInstalled:
                self.forced_obsoletes.extend(self.config.getlist(pkg,"ForcedObsoletes"))
        logging.debug("forced_obsoletes: %s", self.forced_obsoletes)

        # mark packages that are now obsolete (and where not obsolete
        # before) to be deleted. make sure to not delete any foreign
        # (that is, not from ubuntu) packages
        if self.useNetwork:
            # we can only do the obsoletes calculation here if we use a
            # network. otherwise after rewriting the sources.list everything
            # that is not on the CD becomes obsolete (not-downloadable)
            remove_candidates = now_obsolete - self.obsolete_pkgs
        else:
            # initial remove candidates when no network is used should
            # be the demotions to make sure we don't leave potential
            # unsupported software
            remove_candidates = set(self.installed_demotions)
        remove_candidates |= set(self.forced_obsoletes)

        # no go for the unused dependencies
        unused_dependencies = self.cache._getUnusedDependencies()
        logging.debug("Unused dependencies: %s" %" ".join(unused_dependencies))
        remove_candidates |= set(unused_dependencies)

        # see if we actually have to do anything here
        if not self.config.getWithDefault("Distro","RemoveObsoletes", True):
            logging.debug("Skipping RemoveObsoletes as stated in the config")
            remove_candidates = set()
        logging.debug("remove_candidates: '%s'" % remove_candidates)
        logging.debug("Start checking for obsolete pkgs")
        for pkgname in remove_candidates:
            if pkgname not in self.foreign_pkgs:
                self._view.processEvents()
                if not self.cache.tryMarkObsoleteForRemoval(pkgname, remove_candidates, self.foreign_pkgs):
                    logging.debug("'%s' scheduled for remove safe to remove, skipping", pkgname)
        logging.debug("Finish checking for obsolete pkgs")

        # get changes
        changes = self.cache.getChanges()
        logging.debug("The following packages are remove candidates: %s" % " ".join([pkg.name for pkg in changes]))
        summary = _("Remove obsolete packages?")
        actions = [_("_Keep"), _("_Remove")]
        # FIXME Add an explanation about what obsolete packages are
        #explanation = _("")
        if len(changes) > 0 and \
               self._view.confirmChanges(summary, changes, 0, actions, False):
            fprogress = self._view.getFetchProgress()
            iprogress = self._view.getInstallProgress(self.cache)
            try:
                res = self.cache.commit(fprogress,iprogress)
            except (SystemError, IOError), e:
                logging.error("cache.commit() in doPostUpgrade() failed: %s" % e)
                self._view.error(_("Error during commit"),
                                 _("A problem occurred during the clean-up. "
                                   "Please see the below message for more "
                                   "information. "),
                                   "%s" % e)
        self.runPostInstallScripts()

    def runPostInstallScripts(self):
        # now run the post-upgrade fixup scripts (if any)
        for script in self.config.getlist("Distro","PostInstallScripts"):
            logging.debug("Running PostInstallScript: '%s'" % script)
            try:
                self._view.getTerminal().call([script], hidden=True)
            except Exception, e:
                logging.error("got error from PostInstallScript %s (%s)" % (script, e))

    def _rewriteFstab(self):
        " convert /dev/{hd?,scd0} to /dev/cdrom for the feisty upgrade "
        logging.debug("_rewriteFstab()")
        replaced = 0
        lines = []
        # we have one cdrom to convert
        for line in open("/etc/fstab"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception, e:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            # edgy kernel has /dev/cdrom -> /dev/hd?
            # feisty kernel (for a lot of chipsets) /dev/cdrom -> /dev/scd0
            # this breaks static mounting (LP#86424)
            #
            # we convert here to /dev/cdrom only if current /dev/cdrom
            # points to the device in /etc/fstab already. this ensures
            # that we don't break anything or that we get it wrong
            # for systems with two (or more) cdroms. this is ok, because
            # we convert under the old kernel
            if ("iso9660" in fstype and
                device != "/dev/cdrom" and
                os.path.exists("/dev/cdrom") and
                os.path.realpath("/dev/cdrom") == device
                ):
                logging.debug("replacing '%s' " % line)
                line = line.replace(device,"/dev/cdrom")
                logging.debug("replaced line is '%s' " % line)
                replaced += 1
            lines.append(line)
        # we have converted a line (otherwise we would have exited already)
        if replaced > 0:
            logging.debug("writing new /etc/fstab")
            shutil.copy("/etc/fstab","/etc/fstab.edgy")
            open("/etc/fstab","w").write("\n".join(lines))
        return True

    def _checkAdminGroup(self):
        " check if the current sudo user is in the admin group "
        logging.debug("_checkAdminGroup")
        import grp
        try:
            admin_group = grp.getgrnam("admin").gr_mem
        except KeyError, e:
            logging.warning("System has no admin group (%s)" % e)
            subprocess.call(["addgroup","--system","admin"])
        admin_group = grp.getgrnam("admin").gr_mem
        # if the current SUDO_USER is not in the admin group
        # we add him - this is no security issue because
        # the user is already root so adding him to the admin group
        # does not change anything
        if (os.environ.has_key("SUDO_USER") and
            not os.environ["SUDO_USER"] in admin_group):
            admin_user = os.environ["SUDO_USER"]
            logging.info("SUDO_USER=%s is not in admin group" % admin_user)
            cmd = ["usermod","-a","-G","admin",admin_user]
            res = subprocess.call(cmd)
            logging.debug("cmd: %s returned %i" % (cmd, res))
        
    def from_dapperQuirks(self):
        " this works around quirks for dapper->hardy upgrades "
        logging.debug("running Controller.from_dapperQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()
        

    def gutsyQuirks(self):
        """ this function works around quirks in the feisty->gutsy upgrade """
        logging.debug("running Controller.gutsyQuirks handler")

    def feistyQuirks(self):
        """ this function works around quirks in the edgy->feisty upgrade """
        logging.debug("running Controller.feistyQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()
            
    def abort(self):
        """ abort the upgrade, cleanup (as much as possible) """
        if hasattr(self, "sources"):
            self.sources.restoreBackup(self.sources_backup_ext)
        if hasattr(self, "aptcdrom"):
            self.aptcdrom.restoreBackup(self.sources_backup_ext)
        # generate a new cache
        self._view.updateStatus(_("Restoring original system state"))
        self._view.abort()
        self.openCache()
        sys.exit(1)

    def _checkDep(self, depstr):
        " check if a given depends can be satisfied "
        for or_group in apt_pkg.ParseDepends(depstr):
            logging.debug("checking: '%s' " % or_group)
            for dep in or_group:
                depname = dep[0]
                ver = dep[1]
                oper = dep[2]
                if not self.cache.has_key(depname):
                    logging.error("_checkDep: '%s' not in cache" % depname)
                    return False
                inst = self.cache[depname]
                instver = inst.installedVersion
                if (instver != None and
                    apt_pkg.CheckDep(instver,oper,ver) == True):
                    return True
        logging.error("depends '%s' is not satisfied" % depstr)
        return False
                
    def checkViewDepends(self):
        " check if depends are satisfied "
        logging.debug("checkViewDepends()")
        res = True
        # now check if anything from $foo-updates is required
        depends = self.config.getlist("View","Depends")
        depends.extend(self.config.getlist(self._view.__class__.__name__,
                                           "Depends"))
        for dep in depends:
            logging.debug("depends: '%s'", dep)
            res &= self._checkDep(dep)
            if not res:
                # FIXME: instead of error out, fetch and install it
                #        here
                self._view.error(_("Required depends is not installed"),
                                 _("The required dependency '%s' is not "
                                   "installed. " % dep))
                sys.exit(1)
        return res 

    def _verifyBackports(self):
        # run update (but ignore errors in case the countrymirror
        # substitution goes wrong, real errors will be caught later
        # when the cache is searched for the backport packages)
        backportslist = self.config.getlist("PreRequists","Packages")
        i=0
        noCache = apt_pkg.Config.Find("Acquire::http::No-Cache","false")
        maxRetries = self.config.getint("Network","MaxRetries")
        while i < maxRetries:
            self.doUpdate(showErrors=False)
            self.openCache()
            for pkgname in backportslist:
                if not self.cache.has_key(pkgname):
                    logging.error("Can not find backport '%s'" % pkgname)
                    raise NoBackportsFoundException, pkgname
            if self._allBackportsAuthenticated(backportslist):
                break
            # FIXME: move this to some more generic place
            logging.debug("setting a cache control header to turn off caching temporarily")
            apt_pkg.Config.Set("Acquire::http::No-Cache","true")
            i += 1
        if i == maxRetries:
            logging.error("pre-requists item is NOT trusted, giving up")
            return False
        apt_pkg.Config.Set("Acquire::http::No-Cache",noCache)
        return True

    def _allBackportsAuthenticated(self, backportslist):
        if apt_pkg.Config.FindB("APT::Get::AllowUnauthenticated",False) == True:
            logging.warning("skip authentication check because of APT::Get::AllowUnauthenticated==true")
            return True
        for pkgname in backportslist:
            pkg = self.cache[pkgname]                
            for cand in pkg.candidateOrigin:
                if cand.trusted:
                    break
            else:
                return False
        return True

    def isMirror(self, uri):
        " check if uri is a known mirror "
        for mirror in self.valid_mirrors:
            if is_mirror(mirror, uri):
                return True
        return False

    def _getPreReqMirrorLines(self, dumb=False):
        " get sources.list snippet lines for the current mirror "
        lines = ""
        sources = SourcesList(matcherPath=".")
        for entry in sources.list:
            if entry.invalid or entry.disabled:
                continue
            if (entry.type == "deb" and 
                self.isMirror(entry.uri) and
                not entry.uri.startswith("http://security.ubuntu.com") and
                not entry.uri.startswith("http://archive.ubuntu.com") ):
                new_line = "deb %s %s-backports main/debian-installer\n" % (entry.uri, self.fromDist)
                if not new_line in lines:
                    lines += new_line
            if (dumb and entry.type == "deb" and
                "main" in entry.comps):
                lines += "deb %s %s-backports main/debian-installer\n" % (entry.uri, self.fromDist)
        return lines

    def _addPreRequistsSourcesList(self, template, out, dumb=False):
        " add prerequists based on template into the path outfile "
        # go over the sources.list and try to find a valid mirror
        # that we can use to add the backports dir
        logging.debug("writing prerequists sources.list at: '%s' " % out)
        outfile = open(out, "w")
        mirrorlines = self._getPreReqMirrorLines(dumb)
        for line in open(template):
            template = Template(line)
            outline = template.safe_substitute(mirror=mirrorlines)
            outfile.write(outline)
            logging.debug("adding '%s' prerequists" % outline)
        outfile.close()
        return True

    def getRequiredBackports(self):
        " download the backports specified in DistUpgrade.cfg "
        logging.debug("getRequiredBackports()")
        res = True
        backportsdir = os.path.join(os.getcwd(),"backports")
        if not os.path.exists(backportsdir):
            os.mkdir(backportsdir)
        backportslist = self.config.getlist("PreRequists","Packages")

        # if we have them on the CD we are fine
        if self.aptcdrom and not self.useNetwork:
            logging.debug("Searching for pre-requists on CDROM")
            p = os.path.join(self.aptcdrom.cdrompath,
                             "dists/stable/main/dist-upgrader/binary-%s/" % apt_pkg.Config.Find("APT::Architecture"))
            found_pkgs = set()
            for udeb in glob.glob(p+"*_*.udeb"):
                logging.debug("copying pre-req '%s' to '%s'" % (udeb, backportsdir))
                found_pkgs.add(os.path.basename(udeb).split("_")[0])
                shutil.copy(udeb, backportsdir)
            # now check if we got all backports on the CD
            if not set(backportslist) == found_pkgs:
                logging.error("Expected backports: '%s' but got '%s'" % (set(backportslist), found_pkgs))
                return False
            return self.setupRequiredBackports(backportsdir)

        # we support PreRequists/SourcesList-$arch sections here too
        # 
        # logic for mirror finding works list this:     
        # - use the mirror template from the config, then: [done]
        # 
        #  - try to find known mirror (isMirror) and prepend it [done]
        #  - archive.ubuntu.com is always a fallback at the end [done]
        # 
        # see if we find backports with that
        # - if not, try guessing based on URI, Trust and Dist   [done]
        #   in existing sources.list (internal mirror with no
        #   outside connection maybe)
        # 
        # make sure to remove file on cancel
        
        conf_option = "SourcesList"
        if self.config.has_option("PreRequists",conf_option+"-%s" % self.arch):
            conf_option = conf_option + "-%s" % self.arch
        prereq_template = self.config.get("PreRequists",conf_option)
        if not os.path.exists(prereq_template):
            logging.error("sourceslist not found '%s'" % prereq_template)
            return False
        outpath = os.path.join(apt_pkg.Config.FindDir("Dir::Etc::sourceparts"), prereq_template)
        outfile = os.path.join(apt_pkg.Config.FindDir("Dir::Etc::sourceparts"), prereq_template)
        self._addPreRequistsSourcesList(prereq_template, outfile) 
        try:
            self._verifyBackports()
        except NoBackportsFoundException, e:
            self._addPreRequistsSourcesList(prereq_template, outfile, dumb=True) 
            try:
                self._verifyBackports()
            except NoBackportsFoundException, e:
                logging.warning("no backport for '%s' found" % e)
            return False
        
        # save cachedir and setup new one
        cachedir = apt_pkg.Config.Find("Dir::Cache::archives")
        cwd = os.getcwd()
        if not os.path.exists(os.path.join(backportsdir,"partial")):
            os.mkdir(os.path.join(backportsdir,"partial"))
        os.chdir(backportsdir)
        apt_pkg.Config.Set("Dir::Cache::archives",backportsdir)

        # FIXME: sanity check the origin (just for safety)
        for pkgname in backportslist:
            pkg = self.cache[pkgname]
            # look for the right version (backport)
            ver = self.cache._depcache.GetCandidateVer(pkg._pkg)
            if not ver:
                logging.error("No candidate for '%s'" % pkgname)
                os.unlink(outpath)
                return False
            if ver.FileList == None:
                logging.error("No ver.FileList for '%s'" % pkgname)
                os.unlink(outpath)
                return False
            logging.debug("marking '%s' for install" % pkgname)
            # mvo: autoInst is not available on dapper
            #pkg.markInstall(autoInst=False, autoFix=False)
            pkg.markInstall(autoFix=False)

        # mark the backports for upgrade and get them
        fetcher = apt_pkg.GetAcquire(self._view.getFetchProgress())
        pm = apt_pkg.GetPackageManager(self.cache._depcache)

        # now get it
        try:
            res = True
            self.cache._fetchArchives(fetcher, pm)
        except IOError, e:
            logging.error("_fetchArchives returned '%s'" % e)
            res = False

        if res == False:
            logging.warning("_fetchArchives for backports returned False")

        # reset the cache dir
        os.unlink(outpath)
        apt_pkg.Config.Set("Dir::Cache::archives",cachedir)
        os.chdir(cwd)
        return self.setupRequiredBackports(backportsdir)

    def setupRequiredBackports(self, backportsdir):
        " setup the required backports in a evil way "
        if not glob.glob(backportsdir+"/*.udeb"):
            logging.error("no backports found in setupRequiredBackports()")
            return False
        # unpack the backports first
        for deb in glob.glob(backportsdir+"/*.udeb"):
            logging.debug("extracting udeb '%s' " % deb)
            if os.system("dpkg-deb -x %s %s" % (deb, backportsdir)) != 0:
                return False
        # setup some paths to make sure the new stuff is used
        os.environ["LD_LIBRARY_PATH"] = backportsdir+"/usr/lib"
        os.environ["PYTHONPATH"] = backportsdir+"/usr/lib/python%s.%s/site-packages/" % (sys.version_info[0], sys.version_info[1])
        os.environ["PATH"] = "%s:%s" % (backportsdir+"/usr/bin",
                                        os.environ["PATH"])
        # copy log so that it gets not overwritten
        logging.shutdown()
        shutil.copy("/var/log/dist-upgrade/main.log",
                    "/var/log/dist-upgrade/main_pre_req.log")
        # now exec self again
        args = sys.argv + ["--have-prerequists"]
        if self.useNetwork:
            args.append("--with-network")
        else:
            args.append("--without-network")
        # work around kde being clever and removing the x bit
        if not ((S_IMODE(os.stat(sys.argv[0])[ST_MODE]) & S_IXUSR) == S_IXUSR):
            os.chmod(sys.argv[0], 0755)
        os.execve(sys.argv[0],args, os.environ)

    def preDoDistUpgrade(self):
        " this runs right before apt calls out to dpkg "
        # kill update-notifier now to suppress reboot required
        if os.path.exists("/usr/bin/killall"):
            subprocess.call(["killall","-q","update-notifier"])
        # check theme, crux is known to fail badly when upgraded 
        # from dapper
        if (self.fromDist == "dapper" and 
            "DISPLAY" in os.environ and "SUDO_USER" in os.environ):
            out = subprocess.Popen(["sudo","-u", os.environ["SUDO_USER"],
                                    "./theme-switch-helper.py", "-g"],
                                    stdout=subprocess.PIPE).communicate()[0]
            if "Crux" in out:
                subprocess.call(["sudo","-u", os.environ["SUDO_USER"],
                                    "./theme-switch-helper.py", "--defaults"])
        return True

    # this is the core
    def fullUpgrade(self):
        # sanity check (check for ubuntu-desktop, brokenCache etc)
        self._view.updateStatus(_("Checking package manager"))
        self._view.setStep(DistUpgradeView.STEP_PREPARE)

        if not self.prepare():
            logging.error("self.prepared() failed")
            self._view.error(_("Preparing the upgrade failed"),
                             _("Preparing the system for the upgrade "
                               "failed. Please report this as a bug "
                               "against the 'update-manager' "
                               "package and include the files in "
                               "/var/log/dist-upgrade/ "
                               "in the bugreport." ))
            sys.exit(1)

        # mvo: commented out for now, see #54234, this needs to be
        #      refactored to use a arch=any tarball
        if (self.config.has_section("PreRequists") and
            self.options and
            self.options.havePrerequists == False):
            logging.debug("need backports")
            # get backported packages (if needed)
            if not self.getRequiredBackports():
                self._view.error(_("Getting upgrade prerequisites failed"),
                                 _("The system was unable to get the "
                                   "prerequisites for the upgrade. "
                                   "The upgrade will abort now and restore "
                                   "the original system state.\n"
                                   "\n"
                                   "Please report this as a bug "
                                   "against the 'update-manager' "
                                   "package and include the files in "
                                   "/var/log/dist-upgrade/ "
                                   "in the bugreport." ))
                self.abort()

        # run a "apt-get update" now, its ok to ignore errors, 
        # because 
        # a) we disable any third party sources later
        # b) we check if we have valid ubuntu sources later
        #    after we rewrite the sources.list and do a 
        #    apt-get update there too
        # because the (unmodified) sources.list of the user
        # may contain bad/unreachable entries we run only
        # with a single retry
        self.doUpdate(showErrors=False, forceRetries=1)
        self.openCache()

        # do pre-upgrade stuff (calc list of obsolete pkgs etc)
        if not self.doPreUpgrade():
            self.abort()

        # update sources.list
        self._view.setStep(DistUpgradeView.STEP_MODIFY_SOURCES)
        self._view.updateStatus(_("Updating repository information"))
        if not self.updateSourcesList():
            self.abort()

        # add cdrom (if we have one)
        if (self.aptcdrom and
            not self.aptcdrom.add(self.sources_backup_ext)):
            sys.exit(1)

        # then update the package index files
        if not self.doUpdate():
            self.abort()

        # then open the cache (again)
        self._view.updateStatus(_("Checking package manager"))
        self.openCache()
        # now check if we still have some key packages after the update
        # if not something went seriously wrong
        for pkg in self.config.getlist("Distro","BaseMetaPkgs"):
            if not self.cache.has_key(pkg):
                # FIXME: we could offer to add default source entries here,
                #        but we need to be careful to not duplicate them
                #        (i.e. the error here could be something else than
                #        missing sources entries but network errors etc)
                logging.error("No '%s' after sources.list rewrite+update")
                self._view.error(_("Invalid package information"),
                                 _("After your package information was "
                                   "updated the essential package '%s' can "
                                   "not be found anymore.\n"
                                   "This indicates a serious error, please "
                                   "report this bug against the 'update-manager' "
                                   "package and include the files in /var/log/dist-upgrade/ "
                                   "in the bugreport.") % pkg)
                self.abort()

        # calc the dist-upgrade and see if the removals are ok/expected
        # do the dist-upgrade
        self._view.updateStatus(_("Calculating the changes"))
        if not self.askDistUpgrade():
            self.abort()

        # fetch the stuff
        self._view.setStep(DistUpgradeView.STEP_FETCH)
        self._view.updateStatus(_("Fetching"))
        if not self.doDistUpgradeFetching():
            self.abort()

        # now do the upgrade
        self.preDoDistUpgrade()
        self._view.setStep(DistUpgradeView.STEP_INSTALL)
        self._view.updateStatus(_("Upgrading"))
        if not self.doDistUpgrade():
            # run the post install scripts (for stuff like UUID conversion)
            self.runPostInstallScripts()
            # don't abort here, because it would restore the sources.list
            sys.exit(1) 
            
        # do post-upgrade stuff
        self._view.setStep(DistUpgradeView.STEP_CLEANUP)
        self._view.updateStatus(_("Searching for obsolete software"))
        self.doPostUpgrade()

        # done, ask for reboot
        self._view.setStep(DistUpgradeView.STEP_REBOOT)
        self._view.updateStatus(_("System upgrade is complete."))            
        # FIXME should we look into /var/run/reboot-required here?
        if self._view.confirmRestart():
            p = subprocess.Popen("/sbin/reboot")
            sys.exit(0)
        
    def run(self):
        self._view.processEvents()
        self.fullUpgrade()


if __name__ == "__main__":
    from DistUpgradeView import DistUpgradeView
    from DistUpgradeViewText import DistUpgradeViewText
    from DistUpgradeCache import MyCache
    v = DistUpgradeViewText()
    dc = DistUpgradeController(v)
    dc.openCache()
    dc.askDistUpgrade()
    #dc._checkFreeSpace()
    #dc._rewriteFstab()
    #dc._checkAdminGroup()
    #print apt_pkg.Config.Find("APT::Archives::MinAge")
    #dc._rewriteAptPeriodic(2)
