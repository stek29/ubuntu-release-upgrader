#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import print_function

import apt
import apt_pkg
import logging
import os
import unittest

from UpdateManager.Core.MetaRelease import MetaReleaseCore
from DistUpgrade.DistUpgradeFetcherCore import DistUpgradeFetcherCore

# make sure we have a writable location for the meta-release file
os.environ["XDG_CACHE_HOME"] = "/tmp"

CURDIR = os.path.dirname(os.path.abspath(__file__))


def get_new_dist():
    """
    common code to test new dist fetching, get the new dist information
    for hardy+1
    """
    os.system("rm -rf /tmp/update-manager-core/")
    meta = MetaReleaseCore()
    #meta.DEBUG = True
    meta.current_dist_name = "precise"
    meta.METARELEASE_URI = "http://changelogs.ubuntu.com/meta-release"
    meta.downloaded.wait()
    meta._buildMetaReleaseFile()
    meta.download()
    return meta.new_dist


class TestAcquireProgress(apt.progress.base.AcquireProgress):
    " class to test if the acquire progress was run "
    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def pulse(self, acquire):
        self.pulsed = True
        #for item in acquire.items:
        #    print(item, item.destfile, item.desc_uri)
        return True


class TestMetaReleaseCore(unittest.TestCase):

    def setUp(self):
        self.new_dist = None

    def testnewdist(self):
        new_dist = get_new_dist()
        self.assertTrue(new_dist is not None)


class TestDistUpgradeFetcherCore(DistUpgradeFetcherCore):
    " subclass of the DistUpgradeFetcherCore class to make it testable "
    def runDistUpgrader(self):
        " do not actually run the upgrader here "
        return True


class TestDistUpgradeFetcherCoreTestCase(unittest.TestCase):
    testdir = os.path.join(CURDIR, "data-sources-list-test/")
    orig_etc = ''
    orig_sourcelist = ''

    def setUp(self):
        self.new_dist = get_new_dist()
        self.orig_etc = apt_pkg.config.get("Dir::Etc")
        self.orig_sourcelist = apt_pkg.config.get("Dir::Etc::sourcelist")
        apt_pkg.config.set("Dir::Etc", self.testdir)
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list.hardy")

    def tearDown(self):
        apt_pkg.config.set("Dir::Etc", self.orig_etc)
        apt_pkg.config.set("Dir::Etc::sourcelist", self.orig_sourcelist)

    def testfetcher(self):
        progress = TestAcquireProgress()
        fetcher = TestDistUpgradeFetcherCore(self.new_dist, progress)
        #fetcher.DEBUG=True
        res = fetcher.run()
        self.assertTrue(res)
        self.assertTrue(progress.started)
        self.assertTrue(progress.stopped)
        self.assertTrue(progress.pulsed)

    def disabled_because_ftp_is_not_reliable____testfetcher_ftp(self):
        progress = TestAcquireProgress()
        fetcher = TestDistUpgradeFetcherCore(self.new_dist, progress)
        fetcher.current_dist_name = "hardy"
        #fetcher.DEBUG=True
        res = fetcher.run()
        self.assertTrue(res)
        self.assertTrue(fetcher.uri.startswith("ftp://uk.archive.ubuntu.com"))
        self.assertTrue(progress.started)
        self.assertTrue(progress.stopped)
        self.assertTrue(progress.pulsed)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
