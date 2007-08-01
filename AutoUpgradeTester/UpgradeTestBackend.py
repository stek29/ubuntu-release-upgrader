# TargetNonInteractive.py
#
# abstraction for non-interactive backends (like chroot, qemu)
#

from DistUpgradeConfigParser import DistUpgradeConfig

import ConfigParser
import os
import os.path

# refactor the code so that we have
# UpgradeTest - the controler object
# UpgradeTestImage - abstraction for chroot/qemu/xen

class UpgradeTestImage(object):
    def runInTarget(self, command):
        pass
    def copyToImage(self, fromFile, toFile):
        pass
    def copyFromImage(self, fromFile, toFile):
        pass
    def bootstrap(self):
        pass
    def start(self):
        pass
    def stop(self):
        pass

class UpgradeTestBackend(object):
    """ This is a abstrace interface that all backends (chroot, qemu)
        should implement - very basic currently :)
    """

    apt_options = ["-y","--allow-unauthenticated"]

    def __init__(self, profile, basefiledir):
        " init the backend with the given profile "
        # init the dirs
        assert(profile != None)
        self.resultdir = os.path.abspath(os.path.join(os.path.dirname(profile),"result"))
        self.basefilesdir = os.path.abspath(basefiledir)
        # init the rest
        if os.path.exists(profile):
            self.profile = os.path.abspath(profile)
            self.config = DistUpgradeConfig(datadir=os.path.dirname(profile),
                                            name=os.path.basename(profile))
        else:
            raise IOError, "Can't find profile '%s' (%s) " % (profile, os.getcwd())
        
        self.fromDist = self.config.get("Sources","From")
        if self.config.has_option("NonInteractive","Proxy"):
            proxy=self.config.get("NonInteractive","Proxy")
            os.putenv("http_proxy",proxy)
        os.putenv("DEBIAN_FRONTEND","noninteractive")
        self.cachedir = None
        try:
            self.cachedir = self.config.get("NonInteractive","CacheDebs")
        except ConfigParser.NoOptionError:
            pass
        # init a sensible environment (to ensure proper operation if
        # run from cron)
        os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"

    
    def bootstrap(self):
        " bootstaps a pristine install"
        pass

    def upgrade(self):
        " upgrade a given install "
        pass

    def test(self):
        " test if the upgrade was successful "
        pass
