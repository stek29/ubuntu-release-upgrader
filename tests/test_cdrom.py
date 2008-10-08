#!/usr/bin/python

import unittest
import tempfile
import shutil
import sys
import os
import os.path
import apt_pkg
sys.path.insert(0,"../DistUpgrade")

from DistUpgradeAptCdrom import AptCdrom


class testAptCdrom(unittest.TestCase):
    " this test the apt-cdrom implementation "
    
    def testAdd(self):
        p = "./test-data-cdrom"
        apt_pkg.Config.Set("Dir::State::lists","/tmp")
        cdrom = AptCdrom(None, p)
        self.assert_(cdrom._doAdd())



if __name__ == "__main__":
    apt_pkg.init()
    unittest.main()
