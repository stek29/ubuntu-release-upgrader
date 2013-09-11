#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import print_function

import os

import shutil
import subprocess
import apt_pkg
import unittest
from DistUpgrade.DistUpgradeController import (
    DistUpgradeController,
    component_ordering_key,
)
from DistUpgrade.DistUpgradeViewNonInteractive import DistUpgradeViewNonInteractive
from DistUpgrade import DistUpgradeConfigParser
from DistUpgrade.utils import url_downloadable
import logging
import mock

DistUpgradeConfigParser.CONFIG_OVERRIDE_DIR = None

CURDIR = os.path.dirname(os.path.abspath(__file__))


class TestComponentOrdering(unittest.TestCase):

    def test_component_ordering_key_from_set(self):
        self.assertEqual(
            sorted(set(["x", "restricted", "main"]),
                   key=component_ordering_key),
            ["main", "restricted", "x"])

    def test_component_ordering_key_from_list(self):
        self.assertEqual(
            sorted(["x", "main"], key=component_ordering_key),
            ["main", "x"])
        self.assertEqual(
            sorted(["restricted", "main"],
                   key=component_ordering_key),
            ["main", "restricted"])
        self.assertEqual(
            sorted(["main", "restricted"],
                   key=component_ordering_key),
            ["main", "restricted"])
        self.assertEqual(
            sorted(["main", "multiverse", "restricted", "universe"],
                   key=component_ordering_key),
            ["main", "restricted", "universe", "multiverse"])
        self.assertEqual(
            sorted(["a", "main", "multiverse", "restricted", "universe"],
                   key=component_ordering_key),
            ["main", "restricted", "universe", "multiverse", "a"])


class TestSourcesListUpdate(unittest.TestCase):

    testdir = os.path.abspath(CURDIR + "/data-sources-list-test/")

    def setUp(self):
        apt_pkg.config.set("Dir::Etc", self.testdir)
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        if os.path.exists(os.path.join(self.testdir, "sources.list")):
            os.unlink(os.path.join(self.testdir, "sources.list"))

    def test_sources_list_with_nothing(self):
        """
        test sources.list rewrite with nothing in it
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.nothing"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu gutsy main restricted
deb http://archive.ubuntu.com/ubuntu gutsy-updates main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
""")

    def test_sources_list_rewrite(self):
        """
        test regular sources.list rewrite
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.in"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        #print(open(os.path.join(self.testdir,"sources.list")).read())
        self._verifySources("""
# main repo
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb http://de.archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted multiverse
deb http://security.ubuntu.com/ubuntu/ gutsy-security universe
""")
        # check that the backup file was created correctly
        self.assertEqual(0, subprocess.call(
            ["cmp",
             apt_pkg.config.find_file("Dir::Etc::sourcelist") + ".in",
             apt_pkg.config.find_file("Dir::Etc::sourcelist") + ".distUpgrade"
             ]))

    def test_commercial_transition(self):
        """
        test transition of pre-gutsy archive.canonical.com archives
        """
        shutil.copy(os.path.join(self.testdir,
                                 "sources.list.commercial-transition"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        self._verifySources("""
deb http://archive.canonical.com/ubuntu gutsy partner
""")

    def test_powerpc_transition(self):
        """
        test transition of powerpc to ports.ubuntu.com
        """
        arch = apt_pkg.config.find("APT::Architecture")
        apt_pkg.config.set("APT::Architecture", "powerpc")
        shutil.copy(os.path.join(self.testdir, "sources.list.powerpc"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)
        # now test the result
        self._verifySources("""
deb http://ports.ubuntu.com/ubuntu-ports/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://ports.ubuntu.com/ubuntu-ports/ gutsy-security main restricted universe multiverse
""")
        apt_pkg.config.set("APT::Architecture", arch)

    def test_sparc_transition(self):
        """
        test transition of sparc to ports.ubuntu.com
        """
        arch = apt_pkg.config.find("APT::Architecture")
        apt_pkg.config.set("APT::Architecture", "sparc")
        shutil.copy(os.path.join(self.testdir, "sources.list.sparc"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = "gutsy"
        d.toDist = "hardy"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)
        # now test the result
        self._verifySources("""
deb http://ports.ubuntu.com/ubuntu-ports/ hardy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ hardy main restricted multiverse

deb http://ports.ubuntu.com/ubuntu-ports/ hardy-security main restricted universe multiverse
""")
        apt_pkg.config.set("APT::Architecture", arch)

    def testVerifySourcesListEntry(self):
        from aptsources.sourceslist import SourceEntry
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        for scheme in ["http"]:
            entry = "deb %s://archive.ubuntu.com/ubuntu/ precise main universe restricted multiverse" % scheme
            self.assertTrue(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                            "entry '%s' not downloadable" % entry)
            entry = "deb %s://archive.ubuntu.com/ubuntu/ warty main universe restricted multiverse" % scheme
            self.assertFalse(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                             "entry '%s' not downloadable" % entry)
            entry = "deb %s://archive.ubuntu.com/ubuntu/ xxx main" % scheme
            self.assertFalse(d._sourcesListEntryDownloadable(SourceEntry(entry)),
                             "entry '%s' not downloadable" % entry)

    def testEOL2EOLUpgrades(self):
        " test upgrade from EOL release to EOL release "
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir, "sources.list.EOL"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = "warty"
        d.toDist = "hoary"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)
        self._verifySources("""
# main repo
deb http://old-releases.ubuntu.com/ubuntu hoary main restricted multiverse universe
deb-src http://old-releases.ubuntu.com/ubuntu hoary main restricted multiverse

deb http://old-releases.ubuntu.com/ubuntu hoary-security main restricted universe multiverse
""")

    @unittest.skipUnless(url_downloadable(
        "http://us.archive.ubuntu.com/ubuntu", logging.debug),
        "Could not reach mirror")
    def testEOL2SupportedWithMirrorUpgrade(self):
        " test upgrade from a EOL release to a supported release with mirror"
        # Use us.archive.ubuntu.com, because it is available in Canonical's
        # data center, unlike most mirrors.  This lets this test pass when
        # when run in their Jenkins test environment.
        os.environ["LANG"] = "en_US.UTF-8"
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir, "sources.list.EOL2Supported"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = "oneiric"
        d.toDist = "precise"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)
        self._verifySources("""
# main repo
deb http://us.archive.ubuntu.com/ubuntu precise main restricted multiverse universe
deb-src http://us.archive.ubuntu.com/ubuntu precise main restricted multiverse

deb http://us.archive.ubuntu.com/ubuntu precise-security main restricted universe multiverse
""")

    def testEOL2SupportedUpgrade(self):
        " test upgrade from a EOL release to a supported release "
        os.environ["LANG"] = "C"
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        shutil.copy(os.path.join(self.testdir, "sources.list.EOL2Supported"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = "oneiric"
        d.toDist = "precise"
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)
        self._verifySources("""
# main repo
deb http://archive.ubuntu.com/ubuntu precise main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu precise main restricted multiverse

deb http://archive.ubuntu.com/ubuntu precise-security main restricted universe multiverse
""")

    def test_partner_update(self):
        """
        test transition partner repository updates
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.partner"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted universe multiverse

deb http://archive.canonical.com/ubuntu gutsy partner
""")

    def test_private_ppa_transition(self):
        if "RELEASE_UPRADER_ALLOW_THIRD_PARTY" in os.environ:
            del os.environ["RELEASE_UPRADER_ALLOW_THIRD_PARTY"]
        shutil.copy(
            os.path.join(self.testdir,
                         "sources.list.commercial-ppa-uploaders"),
            os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted universe multiverse

# random one
# deb http://user:pass@private-ppa.launchpad.net/random-ppa gutsy main # disabled on upgrade to gutsy

# commercial PPA
deb https://user:pass@private-ppa.launchpad.net/commercial-ppa-uploaders gutsy main
""")

    def test_apt_cacher_and_apt_bittorent(self):
        """
        test transition of apt-cacher/apt-torrent uris
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.apt-cacher"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # now test the result
        self._verifySources("""
deb http://localhost:9977/security.ubuntu.com/ubuntu gutsy-security main restricted universe multiverse
deb http://localhost:9977/archive.canonical.com/ubuntu gutsy partner
deb http://localhost:9977/us.archive.ubuntu.com/ubuntu/ gutsy main
deb http://localhost:9977/archive.ubuntu.com/ubuntu/ gutsy main

deb http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse universe
deb-src http://archive.ubuntu.com/ubuntu/ gutsy main restricted multiverse

deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security universe

deb http://archive.canonical.com/ubuntu gutsy partner
""")

    def test_unicode_comments(self):
        """
        test transition of apt-cacher/apt-torrent uris
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.unicode"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # verify it
        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu gutsy main restricted
deb http://archive.ubuntu.com/ubuntu gutsy-updates main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
# A PPA with a unicode comment
# deb http://ppa.launchpad.net/random-ppa quantal main # ppa of Víctor R. Ruiz (vrruiz) disabled on upgrade to gutsy
""")

    def test_local_mirror(self):
        """
        test that a local mirror with official -backports works (LP:# 1067393)
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.local"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
        v = DistUpgradeViewNonInteractive()
        d = DistUpgradeController(v, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        # verify it
        self._verifySources("""
deb http://192.168.1.1/ubuntu gutsy main restricted
deb http://192.168.1.1/ubuntu gutsy-updates main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
deb http://archive.ubuntu.com/ubuntu gutsy-backports main restricted universe multiverse
""")

    def test_disable_proposed(self):
        """
        Test that proposed is disabled when upgrading to a development
        release.
        """
        shutil.copy(os.path.join(self.testdir,
                    "sources.list.proposed_enabled"),
                    os.path.join(self.testdir, "sources.list"))
        apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
        v = DistUpgradeViewNonInteractive()
        options = mock.Mock()
        options.devel_release = True
        d = DistUpgradeController(v, options, datadir=self.testdir)
        d.openCache(lock=False)
        res = d.updateSourcesList()
        self.assertTrue(res)

        self._verifySources("""
deb http://archive.ubuntu.com/ubuntu gutsy main restricted
deb http://archive.ubuntu.com/ubuntu gutsy-updates main restricted
deb http://security.ubuntu.com/ubuntu/ gutsy-security main restricted
# deb http://archive.ubuntu.com/ubuntu gutsy-proposed universe main multiverse restricted #Not for humans during development stage of release gutsy
""")

    def _verifySources(self, expected):
        sources_file = apt_pkg.config.find_file("Dir::Etc::sourcelist")
        sources_list = open(sources_file).read()
        for l in expected.split("\n"):
            self.assertTrue(
                l in sources_list.split("\n"),
                "expected entry '%s' in sources.list missing. got:\n'''%s'''" %
                (l, sources_list))


if __name__ == "__main__":
    import sys
    for e in sys.argv:
        if e == "-v":
            logging.basicConfig(level=logging.DEBUG)
    unittest.main()
