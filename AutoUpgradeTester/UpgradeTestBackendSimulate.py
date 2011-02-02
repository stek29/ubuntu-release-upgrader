# UpgradeTestBackendSimulate.py
#
# test backend
#

from DistUpgrade.DistUpgradeConfigParser import DistUpgradeConfig

import ConfigParser
import os
import os.path
import tempfile

from UpgradeTestBackend import UpgradeTestBackend

class UpgradeTestBackendSimulate(UpgradeTestBackend):

    def __init__(self, profiledir, resultdir=""):
        super(UpgradeTestBackendSimulate, self).__init__(profiledir, resultdir)
        tmpdir = tempfile.mkdtemp()
        print tmpdir
        self.resultdir = tmpdir + self.resultdir
        os.makedirs(self.resultdir)

    def installPackages(self, pkgs):
        print "simulate installing packages: %s" % ",".join(pkgs)

    def bootstrap(self):
        " bootstaps a pristine install"
        print "simulate running bootstrap"
        return True

    def upgrade(self):
        " upgrade a given install "
        print "simulate running upgrade"
        return True

    def test(self):
        " test if the upgrade was successful "
        print "running post upgrade test"
        return True
