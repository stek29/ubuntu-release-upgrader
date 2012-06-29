#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import unittest
import shutil
import re

from DistUpgrade.xorg_fix_proprietary import (
    comment_out_driver_from_xorg, replace_driver_from_xorg, is_multiseat)

CURDIR = os.path.dirname(os.path.abspath(__file__))


class testOriginMatcher(unittest.TestCase):
    ORIG = CURDIR + "/test-data/xorg.conf.original"
    FGLRX = CURDIR + "/test-data/xorg.conf.fglrx"
    MULTISEAT = CURDIR + "/test-data/xorg.conf.multiseat"
    NEW = CURDIR + "/test-data/xorg.conf"

    def testSimple(self):
        shutil.copy(self.ORIG, self.NEW)
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assertEqual(open(self.NEW).read(), open(self.ORIG).read())

    def testRemove(self):
        shutil.copy(self.FGLRX, self.NEW)
        self.assertTrue("fglrx" in open(self.NEW).read())
        replace_driver_from_xorg("fglrx", "ati", self.NEW)
        self.assertFalse("fglrx" in open(self.NEW).read())

    def testMultiseat(self):
        self.assertFalse(is_multiseat(self.ORIG))
        self.assertFalse(is_multiseat(self.FGLRX))
        self.assertTrue(is_multiseat(self.MULTISEAT))

    def testComment(self):
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
