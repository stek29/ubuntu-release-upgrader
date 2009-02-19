#!/usr/bin/python

import unittest

import os
import os.path
import sys
import time
sys.path.insert(0, "../")

from UpdateManager.Core.MetaRelease import *
from UpdateManager.Core.DistUpgradeFetcherCore import *


def get_new_dist():
    """ 
    common code to test new dist fetching, get the new dist information
    for hardy+1
    """
    meta = MetaReleaseCore()
    #meta.DEBUG = True
    meta.current_dist_name = "hardy"
    meta.METARELEASE_URI = "http://changelogs.ubuntu.com/meta-release"
    while meta.downloading:
        time.sleep(0.1)
    meta._buildMetaReleaseFile()
    meta.download()
    return meta.new_dist

class TestFetchProgress(apt.progress.FetchProgress):
    " class to test if the fetch progress was run "
    def start(self):
        self.started = True
    def stop(self):
        self.stopped = True
    def pulse(self):
        self.pulsed = True
        return True

class TestMetaReleaseCore(unittest.TestCase):

    def setUp(self):
        self.new_dist = None

    def testnewdist(self):
        new_dist = get_new_dist()
        self.assert_(new_dist is not None)

class TestDistUpgradeFetcherCore(DistUpgradeFetcherCore):
    " subclass of the DistUpgradeFetcherCore class to make it testable "
    def runDistUpgrader(self):
        " do not actually run the upgrader here "
        return True

class TestDistUpgradeFetcherCoreTestCase(unittest.TestCase):
    testdir = os.path.abspath("./data-sources-list-test/")

    def setUp(self):
        self.new_dist = get_new_dist()
        apt_pkg.Config.Set("Dir::Etc",self.testdir)
        apt_pkg.Config.Set("Dir::Etc::sourcelist", "sources.list.hardy")
    
    def testfetcher(self):
        progress = TestFetchProgress()
        fetcher = TestDistUpgradeFetcherCore(self.new_dist, progress)
        #fetcher.DEBUG=True
        res = fetcher.run()
        self.assertTrue(res)
        self.assertTrue(progress.started)
        self.assertTrue(progress.stopped)
        self.assertTrue(progress.pulsed)

    def testfetcher_ftp(self):
        progress = TestFetchProgress()
        fetcher = TestDistUpgradeFetcherCore(self.new_dist, progress)
        fetcher.current_dist_name = "hardy"
        #fetcher.DEBUG=True
        res = fetcher.run()
        self.assertTrue(res)
        self.assert_(fetcher.uri.startswith("ftp://uk.archive.ubuntu.com"))
        self.assertTrue(progress.started)
        self.assertTrue(progress.stopped)
        self.assertTrue(progress.pulsed)


if __name__ == '__main__':
    unittest.main()

