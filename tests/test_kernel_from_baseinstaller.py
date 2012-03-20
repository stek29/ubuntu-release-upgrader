#!/usr/bin/python

import os
import subprocess
import sys
import unittest

from mock import Mock,patch

sys.path.insert(0,"../")
from DistUpgrade.DistUpgradeCache import MyCache
from DistUpgrade.DistUpgradeConfigParser import DistUpgradeConfig

class TestKernelBaseinstaller(unittest.TestCase):

    def test_kernel_from_baseinstaller(self):
        # the upgrade expects this 
        os.chdir("../DistUpgrade")
        # get a config
        config = DistUpgradeConfig(".")
        config.set("Files", "LogDir", "/tmp")
        cache = MyCache(config, None, None, lock=False)
        cache._has_kernel_headers_installed = Mock()
        cache._has_kernel_headers_installed.return_value = True
        cache.getKernelsFromBaseInstaller = Mock()
        cache.getKernelsFromBaseInstaller.return_value = \
            ["linux-generic2-pae", "linux-generic2"]
        cache.mark_install = Mock()
        cache.mark_install.return_value = True
        cache._selectKernelFromBaseInstaller()
        #print cache.mark_install.call_args
        calls = cache.mark_install.call_args_list
        self.assertEqual(len(calls), 2)
        cache.mark_install.assert_any_call(
            "linux-generic2-pae", "Selecting new kernel from base-installer")
        cache.mark_install.assert_any_call(
            "linux-headers-generic2-pae", "Selecting new kernel headers from base-installer")
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
