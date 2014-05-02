#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

# Partly based on a script from Review Board, MIT license; but modified to
# act as a unit test.

from __future__ import print_function

import os
import subprocess
import unittest

# FIXME: both ignore listsshould be empty
IGNORE_PEP8 = "W,E125,E126"
IGNORE_FILES = (
    "DistUpgradeViewKDE.py",
    "DistUpgradeViewGtk.py",
    "DistUpgradeViewGtk3.py",
    "DistUpgradeViewText.py",
    "DistUpgradeViewNonInteractive.py",
    "DistUpgradeAufs.py",
    "DistUpgradeAptCdrom.py",
    "DistUpgradeView.py",
    "DistUpgradeController.py",
    "DistUpgradeMain.py",
    "DistUpgradeCache.py",
    "GtkProgress.py",
    "DistUpgradeFetcherSelf.py",
    "DistUpgradePatcher.py",
    "DistUpgradeConfigParser.py",
    "xorg_fix_proprietary.py",
    "source_ubuntu-release-upgrader.py",
    "setup.py",
    "test_sources_list.py",
)


class TestPep8Clean(unittest.TestCase):
    """ ensure that the tree is pep8 clean """

    def test_pep8_clean(self):
        CURDIR = os.path.dirname(os.path.abspath(__file__))
        py_files = set()
        for dirpath, dirs, files in os.walk(os.path.join(CURDIR, "..")):
            for f in files:
                if os.path.splitext(f)[1] != ".py":
                    continue
                    # islink to avoid running pep8 on imported files
                    # that are symlinks to other packages
                if os.path.islink(os.path.join(dirpath, f)):
                    continue
                if f in IGNORE_FILES:
                    continue
                py_files.add(os.path.join(dirpath, f))
        ret_code = subprocess.call(
            ["pep8", "--ignore={0}".format(IGNORE_PEP8)] + list(py_files))
        self.assertEqual(0, ret_code)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
