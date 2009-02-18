# landscape_stub_removal.py 
# Copyright (C) 2009  Canonical, Ltd.
#
# Author: Michael Vogt <mvo@ubuntu.com>
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


import os
import tempfile
import unittest

import landscape_stub_plugin

class MockAptPackage(object):

    def __init__(self, name, installed=True, downloadable=True, installedVersion=""):
        self.name = name
        self.isInstalled = installed
        self.installedDownloadable = downloadable
        self.candidateDownloadable = downloadable
        self.installedVersion = installedVersion
        self.markedRemove = False
        self.markedKeep = False
        self.markedInstall = False
        self._pkg = self

    def markKeep(self):
        self.markedKeep = True

class MockAptCache(dict):

    def add(self, name, **kwargs):
        self[name] = MockAptPackage(name, **kwargs)
    def __iter__(self):
        for pkg in self.values():
            yield pkg
    def markRemove(self, pkgname, reason):
        self[pkgname].markedRemove = True
    def markInstall(self, pkgname, reason):
        self[pkgname].markedInstall = True
        
class MockApplication(object):

    def __init__(self):
        self.apt_cache = MockAptCache()
        self.serverMode = False


class LandscapeStubPluginTests(unittest.TestCase):

    def setUp(self):
        self.plugin = landscape_stub_plugin.LandscapeStubPlugin()
        self.plugin.set_application(MockApplication())

    def tearDown(self):
        pass

    def testLandscapeStub(self):
        self.plugin.app.apt_cache.add("landscape-client", installed=True,
                                      installedVersion="0.1")
        self.plugin.app.apt_cache.add("landscape-common", installed=True,
                                      installedVersion="0.1")
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(sorted(names), sorted([u"deb:landscape-client"]))
        cruft = self.plugin.get_cruft().next()
        cruft.cleanup()
        self.assertEqual(self.plugin.app.apt_cache["landscape-client"].markedRemove, True)
        self.assertEqual(self.plugin.app.apt_cache["landscape-client"].markedInstall, False)
        self.assertEqual(self.plugin.app.apt_cache["landscape-common"].markedKeep, True)
        self.assertEqual(self.plugin.app.apt_cache["landscape-common"].markedInstall, True)
