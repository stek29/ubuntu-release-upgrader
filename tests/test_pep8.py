#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import subprocess
import unittest

# pep8 is overdoing it a bit IMO
IGNORE_PEP8 = "W,E125,E126,E265,E402"
# FIXME: this list should be empty
IGNORE_FILES = (
    "DistUpgradeViewKDE.py",
    "DistUpgradeViewGtk3.py",
    "DistUpgradeViewText.py",
    "DistUpgradeViewNonInteractive.py",
    "DistUpgradeView.py",
    "DistUpgradeController.py",
    "DistUpgradeMain.py",
    "DistUpgradeCache.py",
    "GtkProgress.py",
    "apt_btrfs_snapshot.py",
    "apt_clone.py",
    "distro.py",
    "source_ubuntu-release-upgrader.py",
    "sourceslist.py",
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
