#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import unicode_literals

import os
import tempfile
import unittest

from DistUpgrade.DistUpgradeViewText import DistUpgradeViewText


class TestDistUpradeView(unittest.TestCase):

    def test_show_in_pager_lp1068389(self):
        """Regression test for LP: #1068389"""
        output = tempfile.NamedTemporaryFile()
        os.environ["PAGER"] = "tee %s" % output.name
        v = DistUpgradeViewText()
        v.showInPager("äää")
        with open(output.name, "rb") as fp:
            self.assertEqual(fp.read().decode("utf-8"), "äää")

if __name__ == "__main__":
    unittest.main()
