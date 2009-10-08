#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil
import subprocess

from DistUpgrade.DistUpgradeQuirks import DistUpgradeQuirks

class MockController(object):
    def __init__(self):
        self._view = None

class MockConfig(object):
    pass

class testQuirks(unittest.TestCase):

    def testFglrx(self):
        mock_lspci_good = set(['1002:9714'])
        mock_lspci_bad = set(['8086:ac56'])
        q = DistUpgradeQuirks(MockController(), MockConfig)
        self.assert_(q._supportInModaliases("fglrx",
                                            "../DistUpgrade/modaliases/",
                                            mock_lspci_good) == True)
        self.assert_(q._supportInModaliases("fglrx",
                                            "../DistUpgrade/modaliases/",
                                            mock_lspci_bad) == False)

    def test_cpuHasSSESupport(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-with-sse") == True)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-without-sse") == False)

    def test_patch(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        shutil.copy("./patchdir/foo.orig", "./patchdir/foo")
        q._applyPatches(patchdir="./patchdir")
        self.assertFalse("Hello" in open("./patchdir/foo").read())
        self.assertTrue("Hello" in open("./patchdir/foo.orig").read())

    def test_ntfs_fstab(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        shutil.copy("./test-data/fstab.ntfs.orig", "./test-data/fstab.ntfs")
        self.assertTrue("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 1" in open("./test-data/fstab.ntfs").read())
        q._ntfsFstabFixup(fstab="./test-data/fstab.ntfs")
        self.assertTrue(open("./test-data/fstab.ntfs").read().endswith("0\n"))
        self.assertTrue("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 0" in open("./test-data/fstab.ntfs").read())
        self.assertFalse("UUID=7260D4F760D4C2D1 /media/storage ntfs defaults,nls=utf8,umask=000,gid=46 0 1" in open("./test-data/fstab.ntfs").read())

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
