#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import shutil
import subprocess
import apt
import apt_pkg
import unittest
from DistUpgrade.DistUpgradeControler import DistUpgradeControler
from DistUpgrade.DistUpgradeViewNonInteractive import DistUpgradeViewNonInteractive
import logging

class testSourcesListUpdate(unittest.TestCase):

    testdir = os.path.abspath("./data-sources-list-test/")

    def setUp(self):
        apt_pkg.Config.Set("Dir::Etc",self.testdir)
        apt_pkg.Config.Set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        if os.path.exists(os.path.join(self.testdir, "sources.list")):
            os.unlink(os.path.join(self.testdir, "sources.list"))

    def test_sources_list_rewrite(self):
        """
        test regular sources.list rewrite
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.in"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.Config.Set("Dir::Etc::sourcelist","sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeControler(v,datadir=self.testdir)
        d.openCache()
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
# main repo
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb http://de.archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
""")
        # check that the backup file was created correctly
        self.assert_(subprocess.call(
            ["cmp",
             apt_pkg.Config.FindFile("Dir::Etc::sourcelist")+".in",
             apt_pkg.Config.FindFile("Dir::Etc::sourcelist")+".distUpgrade"
            ]) == 0)

    def test_commercial_transition(self):
        """
        test transition of pre-gutsy archive.canonical.com archives
        """
        shutil.copy(os.path.join(self.testdir,"sources.list.commercial-transition"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.Config.Set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeControler(v,datadir=self.testdir)
        d.openCache()
        res = d.updateSourcesList()
        self.assert_(res == True)

        # now test the result
        self._verifySources("""
deb http://archive.canonical.com/ubuntu gutsy partner
""")
        
    def test_powerpc_transition(self):
        """ 
        test transition of powerpc to ports.ubuntu.com
        """
        arch = apt_pkg.Config.Find("APT::Architecture")
        apt_pkg.Config.Set("APT::Architecture","powerpc")
        shutil.copy(os.path.join(self.testdir,"sources.list.powerpc"),
                    os.path.join(self.testdir,"sources.list"))
        apt_pkg.Config.Set("Dir::Etc::sourceparts",os.path.join(self.testdir,"sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeControler(v,datadir=self.testdir)
        d.openCache()
        res = d.updateSourcesList()
        self.assert_(res == True)
        # now test the result
        self._verifySources("""
deb http://ports.ubuntu.com/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
""")
        apt_pkg.Config.Set("APT::Architecture",arch)
        
        
    def _verifySources(self, expected):
        sources_list = open(apt_pkg.Config.FindFile("Dir::Etc::sourcelist")).read()
        for l in expected.split("\n"):
            self.assert_(l in sources_list,
                         "expected entry '%s' in sources.list missing" % l)
        

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
