#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import print_function

import unittest

from DistUpgrade.GtkProgress import GtkAcquireProgress
from UpdateManager.UpdateManager import UpdateManager
from UpdateManager.MetaReleaseGObject import MetaRelease
from DistUpgrade.DistUpgradeFetcher import DistUpgradeFetcherGtk


def _(s):
    return s

# FIXME: use dogtail
# something like (needs to run as a seperate process):
#
# from dogtail.procedural import *
#         focus.application('displayconfig-gtk')
#        focus.frame('Screen and Graphics Preferences')
#        click("Plug 'n' Play", roleName='push button')
#        focus.window('Choose Screen')
#        select('Flat Panel 1024x768', roleName='table cell')
#        keyCombo("Return")
#        click('OK', roleName='push button')


class TestMetaReleaseGUI(unittest.TestCase):
    def setUp(self):
        self.new_dist = None

    def new_dist_available(self, meta_release, upgradable_to):
        #print("new dist: ", upgradable_to.name)
        #print("new dist: ", upgradable_to.version)
        #print("meta release: %s" % meta_release)
        self.new_dist = upgradable_to

    def testnewdist(self):
        meta = MetaRelease()
        uri = "http://changelogs.ubuntu.com/meta-release-unit-testing"
        meta.METARELEASE_URI = uri
        meta.connect("new_dist_available", self.new_dist_available)
        meta.download()
        self.assertTrue(meta.downloaded.is_set())
        no_new_information = meta.check()
        self.assertFalse(no_new_information)
        self.assertTrue(self.new_dist is not None)


class TestReleaseUpgradeFetcherGUI(unittest.TestCase):
    def _new_dist_available(self, meta_release, upgradable_to):
        self.new_dist = upgradable_to

    def setUp(self):
        meta = MetaRelease()
        uri = "http://changelogs.ubuntu.com/meta-release-unit-testing"
        meta.METARELEASE_URI = uri
        meta.connect("new_dist_available", self._new_dist_available)
        meta.download()
        self.assertTrue(meta.downloaded.is_set())
        no_new_information = meta.check()
        self.assertFalse(no_new_information)
        self.assertTrue(self.new_dist is not None)

    def testdownloading(self):
        parent = UpdateManager("/usr/share/update-manager/", None)
        progress = GtkAcquireProgress(parent,
                                      "/usr/share/update-manager/",
                                      _("Downloading the upgrade "
                                        "tool"),
                                      _("The upgrade tool will "
                                        "guide you through the "
                                        "upgrade process."))
        fetcher = DistUpgradeFetcherGtk(self.new_dist, parent=parent,
                                        progress=progress,
                                        datadir="/usr/share/update-manager/")
        self.assertTrue(fetcher.showReleaseNotes())
        self.assertTrue(fetcher.fetchDistUpgrader())
        self.assertTrue(fetcher.extractDistUpgrader())
        fetcher.script = fetcher.tmpdir + "/gutsy"
        #fetcher.verifyDistUprader()
        self.assertTrue(fetcher.authenticate())
        self.assertTrue(fetcher.runDistUpgrader())


if __name__ == '__main__':
    unittest.main()
