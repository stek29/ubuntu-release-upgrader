#!/usr/bin/python

import unittest

import apt_pkg
import logging
import os
import sys

sys.path.insert(0, "../")
from UpdateManager.Core.utils import init_proxy

class TestInitProxy(unittest.TestCase):

    def testinitproxy(self):
        from gi.repository import Gio
        proxy = "http://10.0.2.2:3128"
        try:
            del os.environ["http_proxy"]
        except KeyError: 
            pass
        apt_pkg.config.set("Acquire::http::proxy", proxy)
        settings = Gio.Settings("com.ubuntu.update-manager")
        detected_proxy = init_proxy(settings)
        self.assertEqual(detected_proxy, proxy)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        logging.basicConfig(level=logging.DEBUG)
    unittest.main()
