#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import hashlib
import mock
import unittest
import shutil
import subprocess

from DistUpgrade.DistUpgradeQuirks import DistUpgradeQuirks

class MockController(object):
    def __init__(self):
        self._view = None

class MockConfig(object):
    pass

class TestQuirks(unittest.TestCase):

    def test_parse_from_modaliases_header(self):
        pkgrec = { "Package" : "foo",
                   "Modaliases" : "modules1(pci:v00001002d00006700sv*sd*bc03sc*i*, pci:v00001002d00006701sv*sd*bc03sc*i*), module2(pci:v00001002d00006702sv*sd*bc03sc*i*, pci:v00001001d00006702sv*sd*bc03sc*i*)"
                 }
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        self.assertEqual(q._parse_modaliases_from_pkg_header({}), [])
        self.assertEqual(q._parse_modaliases_from_pkg_header(pkgrec),
                         [("modules1",
                           ["pci:v00001002d00006700sv*sd*bc03sc*i*", "pci:v00001002d00006701sv*sd*bc03sc*i*"]),
                         ("module2",
                          ["pci:v00001002d00006702sv*sd*bc03sc*i*", "pci:v00001001d00006702sv*sd*bc03sc*i*"]) ])

    def testFglrx(self):
        mock_lspci_good = set(['1002:9714'])
        mock_lspci_bad = set(['8086:ac56'])
        config = mock.Mock()
        cache = apt.Cache()
        controller = mock.Mock()
        controller.cache = cache
        q = DistUpgradeQuirks(controller, config)
        self.assert_(q._supportInModaliases("fglrx",
                                            mock_lspci_good) == True)
        self.assert_(q._supportInModaliases("fglrx",
                                            mock_lspci_bad) == False)

    def test_cpuHasSSESupport(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-with-sse") == True)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-without-sse") == False)

    def test_cpu_is_i686(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        q.arch = "i386"
        self.assertTrue(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-with-sse"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-without-cmov"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-i586"))
        self.assertFalse(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-i486"))
        self.assertTrue(q._cpu_is_i686_and_has_cmov("test-data/cpuinfo-via-c7m"))

    def test_patch(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        shutil.copy("./patchdir/foo_orig", "./patchdir/foo")
        shutil.copy("./patchdir/fstab_orig", "./patchdir/fstab")
        shutil.copy("./patchdir/pycompile_orig", "./patchdir/pycompile")
        q._applyPatches(patchdir="./patchdir")
        # simple case is foo
        self.assertFalse("Hello" in open("./patchdir/foo").read())
        self.assertTrue("Hello" in open("./patchdir/foo_orig").read())
        md5 = hashlib.md5()
        md5.update(open("./patchdir/foo").read())
        self.assertEqual(md5.hexdigest(), "52f83ff6877e42f613bcd2444c22528c")
        # more complex example fstab
        md5 = hashlib.md5()
        md5.update(open("./patchdir/fstab").read())
        self.assertEqual(md5.hexdigest(), "c56d2d038afb651920c83106ec8dfd09")
        # most complex example
        md5 = hashlib.md5()
        md5.update(open("./patchdir/pycompile").read())
        self.assertEqual(md5.hexdigest(), "97c07a02e5951cf68cb3f86534f6f917")

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
