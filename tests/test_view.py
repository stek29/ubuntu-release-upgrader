#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

from __future__ import unicode_literals

import os
import tempfile
import unittest

from mock import patch

from DistUpgrade.DistUpgradeViewText import DistUpgradeViewText


class TestDistUpradeView(unittest.TestCase):

    def test_prompt_with_unicode_lp1071388(self):
        with tempfile.TemporaryFile() as f:
            f.write("some unicode: ä".encode("utf-8"))
            f.flush()
            f.seek(0)
            with patch("sys.stdin", f):
                v = DistUpgradeViewText()
                res = v.askYesNoQuestion("Some text", "some more")
                self.assertEqual(res, False)

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
