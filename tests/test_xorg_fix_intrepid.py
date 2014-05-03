#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import unittest
import shutil
import re

from DistUpgrade.xorg_fix_proprietary import (
    comment_out_driver_from_xorg,
    replace_driver_from_xorg,
)

CURDIR = os.path.dirname(os.path.abspath(__file__))


class OriginMatcherTestCase(unittest.TestCase):

    ORIG = CURDIR + "/test-data/xorg.conf.original"
    FGLRX = CURDIR + "/test-data/xorg.conf.fglrx"
    MULTISEAT = CURDIR + "/test-data/xorg.conf.multiseat"
    NEW = CURDIR + "/test-data/xorg.conf"

    def test_simple(self):
        shutil.copy(self.ORIG, self.NEW)
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assertEqual(open(self.NEW).read(), open(self.ORIG).read())

    def test_remove(self):
        shutil.copy(self.FGLRX, self.NEW)
        self.assertTrue("fglrx" in open(self.NEW).read())
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assertFalse("fglrx" in open(self.NEW).read())

    def test_omment(self):
        shutil.copy(self.FGLRX, self.NEW)
        comment_out_driver_from_xorg("fglrx", self.NEW)
        for line in open(self.NEW):
            if re.match('^#.*Driver.*fglrx', line):
                import logging
                logging.info("commented out line found")
                break
        else:
            raise Exception("commenting the line did *not* work")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
