#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import print_function

import unittest
import tempfile
import shutil
import os.path
import apt_pkg

from DistUpgrade.DistUpgradeController import (
    DistUpgradeController, NoBackportsFoundException)
from DistUpgrade.DistUpgradeView import DistUpgradeView
from DistUpgrade import DistUpgradeConfigParser

DistUpgradeConfigParser.CONFIG_OVERRIDE_DIR = None

CURDIR = os.path.dirname(os.path.abspath(__file__))


class testPreRequists(unittest.TestCase):
    " this test the prerequists fetching "

    testdir = os.path.abspath(CURDIR + "/data-sources-list-test/")

    orig_etc = ''
    orig_sourceparts = ''
    orig_state = ''
    orig_status = ''
    orig_trusted = ''

    def setUp(self):
        self.orig_etc = apt_pkg.config.get("Dir::Etc")
        self.orig_sourceparts = apt_pkg.config.get("Dir::Etc::sourceparts")
        self.orig_state = apt_pkg.config.get("Dir::State")
        self.orig_status = apt_pkg.config.get("Dir::State::status")
        self.orig_trusted = apt_pkg.config.get("APT::GPGV::TrustedKeyring")

        apt_pkg.config.set("Dir::Etc", self.testdir)
        apt_pkg.config.set("Dir::Etc::sourceparts",
                           os.path.join(self.testdir, "sources.list.d"))
        self.dc = DistUpgradeController(DistUpgradeView(),
                                        datadir=self.testdir)

    def tearDown(self):
        apt_pkg.config.set("Dir::Etc", self.orig_etc)
        apt_pkg.config.set("Dir::Etc::sourceparts", self.orig_sourceparts)
        apt_pkg.config.set("Dir::State", self.orig_state)
        apt_pkg.config.set("Dir::State::status", self.orig_status)
        apt_pkg.config.set("APT::GPGV::TrustedKeyring", self.orig_trusted)

    def testPreReqSourcesListAddingSimple(self):
        " test adding the prerequists when a mirror is known "
        shutil.copy(os.path.join(self.testdir, "sources.list.in"),
                    os.path.join(self.testdir, "sources.list"))
        template = os.path.join(self.testdir, "prerequists-sources.list.in")
        out = os.path.join(self.testdir, "sources.list.d",
                           "prerequists-sources.list")
        self.dc._addPreRequistsSourcesList(template, out)
        self.assertTrue(os.path.getsize(out))
        self._verifySources(out, "\n"
                                 "deb http://old-releases.ubuntu.com/ubuntu/ "
                                 "feisty-backports main/debian-installer\n"
                                 "\n")

    def testPreReqSourcesListAddingNoMultipleIdenticalLines(self):
        """ test adding the prerequists and ensure that no multiple
            identical lines are added
        """
        shutil.copy(os.path.join(self.testdir, "sources.list.no_archive_u_c"),
                    os.path.join(self.testdir, "sources.list"))
        template = os.path.join(self.testdir, "prerequists-sources.list.in")
        out = os.path.join(self.testdir, "sources.list.d",
                           "prerequists-sources.list")
        self.dc._addPreRequistsSourcesList(template, out)
        self.assertTrue(os.path.getsize(out))
        self._verifySources(out, "\n"
                                 "deb http://old-releases.ubuntu.com/ubuntu/ "
                                 "feisty-backports main/debian-installer\n"
                                 "\n")

    def testVerifyBackportsNotFound(self):
        " test the backport verification "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir, "sources.list.minimal"),
                    os.path.join(self.testdir, "sources.list"))
        tmpdir = tempfile.mkdtemp()
        # unset sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        # write empty status file
        open(tmpdir + "/status", "w")
        os.makedirs(tmpdir + "/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir + "/status")
        self.dc.openCache(lock=False)
        exp = False
        try:
            res = self.dc._verifyBackports()
            print(res)
        except NoBackportsFoundException:
            exp = True
        self.assertTrue(exp)

    def disabled__as_jaunty_is_EOL_testVerifyBackportsValid(self):
        " test the backport verification "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir, "sources.list.minimal"),
                    os.path.join(self.testdir, "sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",
                           self.testdir + "/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(self.testdir, "prerequists-sources.list.in")
        out = os.path.join(tmpdir, "prerequists-sources.list")
        # write empty status file
        open(tmpdir + "/status", "w")
        os.makedirs(tmpdir + "/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir + "/status")
        self.dc._addPreRequistsSourcesList(template, out)
        self.dc.openCache(lock=False)
        res = self.dc._verifyBackports()
        self.assertTrue(res)

    def disabled__as_jaunty_is_EOL_testVerifyBackportsNoValidMirror(self):
        " test the backport verification with no valid mirror "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir, "sources.list.no_valid_mirror"),
                    os.path.join(self.testdir, "sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",
                           self.testdir + "/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(
            self.testdir,
            "prerequists-sources.list.in.no_archive_falllback")
        out = os.path.join(tmpdir, "prerequists-sources.list")
        # write empty status file
        open(tmpdir + "/status", "w")
        os.makedirs(tmpdir + "/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir + "/status")
        self.dc._addPreRequistsSourcesList(template, out, dumb=True)
        self.dc.openCache(lock=False)
        res = self.dc._verifyBackports()
        self.assertTrue(res)

    def disabled__as_jaunty_is_EOL_testVerifyBackportsNoValidMirror2(self):
        " test the backport verification with no valid mirror "
        # only minimal stuff in sources.list to speed up tests
        shutil.copy(os.path.join(self.testdir, "sources.list.no_valid_mirror"),
                    os.path.join(self.testdir, "sources.list"))
        tmpdir = tempfile.mkdtemp()
        #apt_pkg.config.set("Debug::pkgAcquire::Auth","true")
        #apt_pkg.config.set("Debug::Acquire::gpgv","true")
        apt_pkg.config.set("APT::GPGV::TrustedKeyring",
                           self.testdir + "/trusted.gpg")
        # set sourceparts
        apt_pkg.config.set("Dir::Etc::sourceparts", tmpdir)
        template = os.path.join(self.testdir,
                                "prerequists-sources.list.in.broken")
        out = os.path.join(tmpdir, "prerequists-sources.list")
        # write empty status file
        open(tmpdir + "/status", "w")
        os.makedirs(tmpdir + "/lists/partial")
        apt_pkg.config.set("Dir::State", tmpdir)
        apt_pkg.config.set("Dir::State::status", tmpdir + "/status")
        try:
            self.dc._addPreRequistsSourcesList(template, out, dumb=False)
            self.dc.openCache(lock=False)
            self.dc._verifyBackports()
        except NoBackportsFoundException:
            exp = True
        self.assertTrue(exp)

    def _verifySources(self, filename, expected):
        sources_list = open(filename).read()
        for l in expected.split("\n"):
            if l:
                self.assertTrue(l in sources_list,
                                "expected entry '%s' in '%s' missing, "
                                "got:\n%s" % (l, filename,
                                              open(filename).read()))

if __name__ == "__main__":
    unittest.main()
