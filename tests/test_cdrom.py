#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import print_function

import apt_pkg
import os
import tempfile
import unittest

from mock import Mock

from DistUpgrade.DistUpgradeAptCdrom import AptCdrom

CURDIR = os.path.dirname(os.path.abspath(__file__))


class TestAptCdrom(unittest.TestCase):
    " this test the apt-cdrom implementation "

#    def testAdd(self):
#        p = CURDIR + "/test-data-cdrom"
#        apt_pkg.config.set("Dir::State::lists","/tmp")
#        cdrom = AptCdrom(None, p)
#        self.assertTrue(cdrom._doAdd())

    def testWriteDatabase(self):
        expect = \
            "CD::36e3f69081b7d10081d167b137886a71-2 " \
            "\"Ubuntu 8.10 _Intrepid Ibex_ - Beta amd64 (20080930.4)\";\n" \
            "CD::36e3f69081b7d10081d167b137886a71-2::Label " \
            "\"Ubuntu 8.10 _Intrepid Ibex_ - Beta amd64 (20080930.4)\";\n"
        p = CURDIR + "/test-data-cdrom/"
        database = CURDIR + "/test-data-cdrom/cdrom.list"
        apt_pkg.config.set("Dir::State::cdroms", database)
        apt_pkg.config.set("Acquire::cdrom::mount", p)
        apt_pkg.config.set("APT::CDROM::NoMount", "true")
        if os.path.exists(database):
            os.unlink(database)
        cdrom = AptCdrom(None, p)
        cdrom._writeDatabase()
        self.assertEqual(expect, open(database).read())

    def testScanCD(self):
        p = CURDIR + "/test-data-cdrom"
        cdrom = AptCdrom(None, p)
        (p, s, i18n) = cdrom._scanCD()
        self.assertTrue(len(p) > 0 and len(s) > 0 and len(i18n) > 0,
                        "failed to scan packages files (%s) (%s)" % (p, s))
        #print(p,s,i18n)

    def testDropArch(self):
        p = CURDIR + "/test-data-cdrom"
        cdrom = AptCdrom(None, p)
        (p, s, i18n) = cdrom._scanCD()
        self.assertTrue(len(cdrom._dropArch(p)) < len(p),
                        "drop arch did not drop (%s) < (%s)" % (
                            len(cdrom._dropArch(p)), len(p)))

    def testDiskName(self):
        " read and escape the disskname"
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        s = cdrom._readDiskName()
        self.assertEqual(
            "Ubuntu 8.10 _Intrepid Ibex_ - Beta amd64 (20080930.4)", s,
            "_readDiskName failed (got %s)" % s)

    def testGenerateSourcesListLine(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        p = cdrom._dropArch(p)
        line = cdrom._generateSourcesListLine(cdrom._readDiskName(), p)
        #print(line)
        self.assertEqual("deb cdrom:[Ubuntu 8.10 _Intrepid Ibex_ - Beta amd64 "
                         "(20080930.4)]/ intrepid restricted", line,
                         "deb line wrong (got %s)" % line)

    def testCopyi18n(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        p = cdrom._dropArch(p)
        d = tempfile.mkdtemp()
        cdrom._copyTranslations(i18n, d)
        self.assertTrue(
            os.path.exists(os.path.join(d,
                                        "Ubuntu%208.10%20%5fIntrepid%20Ibex"
                                        "%5f%20-%20Beta%20amd64%20(20080930.4)"
                                        "_dists_intrepid_main_i18n_"
                                        "Translation-be")),
            "no outfile in '%s'" % os.listdir(d))

    def testCopyPackages(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        p = cdrom._dropArch(p)
        d = tempfile.mkdtemp()
        cdrom._copyPackages(p, d)
        self.assertTrue(
            os.path.exists(os.path.join(d,
                                        "Ubuntu%208.10%20%5fIntrepid%20Ibex"
                                        "%5f%20-%20Beta%20amd64%20(20080930.4)"
                                        "_dists_intrepid_restricted_binary-"
                                        "amd64_Packages")),
            "no outfile in '%s'" % os.listdir(d))

    def testVerifyRelease(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        res = cdrom._verifyRelease(s)
        self.assertTrue(res)

    def testCopyRelease(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        d = tempfile.mkdtemp()
        cdrom._copyRelease(s, d)
        self.assertTrue(
            os.path.exists(os.path.join(d,
                                        "Ubuntu%208.10%20%5fIntrepid%20Ibex"
                                        "%5f%20-%20Beta%20amd64%20(20080930.4)"
                                        "_dists_intrepid_Release")),
            "no outfile in '%s' (%s)" % (d, os.listdir(d)))

    def testSourcesList(self):
        cdrom = AptCdrom(None, CURDIR + "/test-data-cdrom")
        (p, s, i18n) = cdrom._scanCD()
        p = cdrom._dropArch(p)
        line = cdrom._generateSourcesListLine(cdrom._readDiskName(), p)
        self.assertEqual("deb cdrom:[Ubuntu 8.10 _Intrepid Ibex_ - Beta amd64 "
                         "(20080930.4)]/ intrepid restricted",
                         line,
                         "sources.list line incorrect, got %s" % line)

    def test_comment_out(self):
        tmpdir = tempfile.mkdtemp()
        sourceslist = os.path.join(tmpdir, "sources.list")
        open(sourceslist, "w")
        apt_pkg.config.set("dir::etc::sourcelist", sourceslist)
        apt_pkg.config.set("dir::state::lists", tmpdir)
        view = Mock()
        cdrom = AptCdrom(view, CURDIR + "/test-data-cdrom")
        cdrom.add()
        cdrom.comment_out_cdrom_entry()
        for line in open(sourceslist):
            self.assertTrue(line.startswith("#"))
        self.assertEqual(len(open(sourceslist).readlines()), 2)


if __name__ == "__main__":
    apt_pkg.init()
    apt_pkg.config.set("APT::Architecture", "amd64")
    unittest.main()
