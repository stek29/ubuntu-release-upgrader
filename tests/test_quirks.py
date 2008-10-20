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

    def test_cpuHasSSESupport(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-with-sse") == True)
        self.assert_(q._cpuHasSSESupport(cpuinfo="test-data/cpuinfo-without-sse") == False)

if __name__ == "__main__":
    unittest.main()
