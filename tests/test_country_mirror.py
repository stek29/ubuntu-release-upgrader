#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import unittest

from DistUpgrade.DistUpgradeFetcherCore import country_mirror

CURDIR = os.path.dirname(os.path.abspath(__file__))


class testCountryMirror(unittest.TestCase):

    def testSimple(self):
        # empty
        try:
            del os.environ["LANG"]
        except KeyError:
            pass
        self.assertEqual(country_mirror(), '')
        # simple
        os.environ["LANG"] = 'de'
        self.assertEqual(country_mirror(), 'de.')
        # more complicated
        os.environ["LANG"] = 'en_DK.UTF-8'
        self.assertEqual(country_mirror(), 'dk.')
        os.environ["LANG"] = 'fr_FR@euro.ISO-8859-15'
        self.assertEqual(country_mirror(), 'fr.')


if __name__ == "__main__":
    unittest.main()
