#!/usr/bin/python

import logging
import os
import sys
import unittest

from mock import patch, Mock

sys.path.insert(0, "../")
from UpdateManager.Core.MyCache import MyCache
from UpdateManager.Core.MyCache import MyCache

class TestCache(unittest.TestCase):

    def setUp(self):
        self.cache = MyCache(None)

    def test_https_and_creds_in_changelog_uri(self):
        # credentials in https locations are not supported as they can
        # be man-in-the-middled because of the lack of cert checking in
        # urllib2
        pkgname = "apt"
        uri = "https://user:pass$word@ubuntu.com/foo/bar"
        self.cache._guess_third_party_changelogs_uri_by_binary = Mock()
        self.cache._guess_third_party_changelogs_uri_by_binary.return_value = uri
        self.cache._guess_third_party_changelogs_uri_by_source = Mock()
        self.cache._guess_third_party_changelogs_uri_by_source.return_value = uri
        self.cache.all_changes[pkgname] = "header\n"
        self.cache._fetch_changelog_for_third_party_package(pkgname)
        self.assertEqual(
            self.cache.all_changes[pkgname], 
            "header\n"
            "This update does not come from a source that supports changelogs.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        logging.basicConfig(level=logging.DEBUG)
    unittest.main()
