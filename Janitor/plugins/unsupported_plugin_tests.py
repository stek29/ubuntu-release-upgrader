# unsupported_plugin_tests.py - unit tests for unsupported_plugin.py
# Copyright (C) 2008  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import unittest

import unsupported_plugin


class MockAptPackage(object):

    def __init__(self, name, installed=True, downloadable=True, versions=[]):
        self.name = name
        self.isInstalled = installed
        self.installedDownloadable = downloadable
        self.candidateDownloadable = downloadable
        self.VersionList = versions
        self._pkg = self


class MockAptCache(dict):

    def add(self, name, **kwargs):
        self[name] = MockAptPackage(name, **kwargs)

    def __iter__(self):
        for pkg in self.values():
            yield pkg
        
        
class MockApplication(object):

    def __init__(self):
        self.apt_cache = MockAptCache()


class UnsupportedPackagesPlugin(unittest.TestCase):

    def setUp(self):
        self.app = MockApplication()
        self.app.apt_cache.add("dash")
        self.app.apt_cache.add("gzip")
        self.plugin = unsupported_plugin.UnsupportedPackagesPlugin()
        self.plugin.set_application(self.app)

    def testConsidersUninstalledPackageToBeSupported(self):
        pkg = MockAptPackage("foo", installed=False)
        self.assert_(self.plugin.is_supported(pkg))

    def testConsidersUndownloadablePackageToBeUnsupported(self):
        pkg = MockAptPackage("foo", downloadable=False)
        self.assertFalse(self.plugin.is_supported(pkg))

    def testConsidersUndownloadablePackageWithManyVersionsToBeSupported(self):
        pkg = MockAptPackage("foo", downloadable=False, versions=[1,2])
        self.assert_(self.plugin.is_supported(pkg))

    def testConsidersInstalledAndDownloadablePackageToBeSupported(self):
        pkg = MockAptPackage("foo")
        self.assert_(self.plugin.is_supported(pkg))

    def testFindsTheRightCruft(self):
        self.app.apt_cache.add("foo")
        self.app.apt_cache.add("bar", downloadable=False)
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(names, ["deb:bar"])

    def testFindsUname(self):
        self.assert_(self.plugin.uname)

    def testConsidersObsoleteKernelAsCruft(self):
        self.app.apt_cache.add("linux-image-1.2.13", downloadable=False)
        self.plugin.uname = "2.6.27"
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(names, ["deb:linux-image-1.2.13"])

    def testDoesNotConsiderRunningKernelToBeCruft(self):
        self.app.apt_cache.add("linux-image-1.2.13", downloadable=False)
        self.plugin.uname = "1.2.13"
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(names, [])
