#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import unittest

from contextlib import contextmanager
from DistUpgrade.DistUpgradeFetcherCore import country_mirror

CURDIR = os.path.dirname(os.path.abspath(__file__))


class testCountryMirror(unittest.TestCase):

    @contextmanager
    def _hackenv(self, envar, new_value):
        """Hack the environment temporarily, then reset it."""
        old_value = os.getenv(envar)
        if new_value is None:
            if envar in os.environ:
                del os.environ[envar]
        else:
            os.environ[envar] = new_value
        try:
            yield
        finally:
            if old_value is None:
                if envar in os.environ:
                    del os.environ[envar]
            else:
                os.environ[envar] = old_value

    def testSimple(self):
        # empty
        with self._hackenv('LANG', None):
            self.assertEqual(country_mirror(), '')
        # simple
        with self._hackenv('LANG', 'de'):
            self.assertEqual(country_mirror(), 'de.')
        # more complicated
        with self._hackenv('LANG', 'en_DK.UTF-8'):
            self.assertEqual(country_mirror(), 'dk.')
        with self._hackenv('LANG', 'fr_FR@euro.ISO-8859-15'):
            self.assertEqual(country_mirror(), 'fr.')


if __name__ == "__main__":
    unittest.main()
