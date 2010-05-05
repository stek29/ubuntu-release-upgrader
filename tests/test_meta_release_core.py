#!/usr/bin/python

import unittest

import os
import os.path
import sys
import time
sys.path.insert(0, "../")

from UpdateManager.Core.MetaRelease import *
from UpdateManager.Core.DistUpgradeFetcherCore import *


def get_new_dist(current_release):
    """ 
    common code to test new dist fetching, get the new dist information
    for hardy+1
    """
    meta = MetaReleaseCore()
    #meta.DEBUG = True
    meta.current_dist_name = current_release
    fake_metarelease = os.path.join(os.getcwd(), "test-data", "meta-release")
    meta.METARELEASE_URI = "file://%s" % fake_metarelease
    while meta.downloading:
        time.sleep(0.1)
    meta._buildMetaReleaseFile()
    meta.download()
    return meta.new_dist

class TestMetaReleaseCore(unittest.TestCase):

    def setUp(self):
        self.new_dist = None

    def testnewdist(self):
        new_dist = get_new_dist("hardy")
        self.assert_(new_dist.name == "intrepid")



if __name__ == '__main__':
    unittest.main()

