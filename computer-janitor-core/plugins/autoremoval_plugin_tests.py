# autoremoval_plugin_tests.py - unittests for autoremoval_plugin.py
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

import autoremoval_plugin


class MockAptPackage(object):

    def __init__(self, name, autoremovable):
        self.name = name
        self.isAutoRemovable = autoremovable


class MockAptCache(list):

    def add(self, name, autoremovable):
        self.append(MockAptPackage(name, autoremovable))
        
        
class MockApplication(object):

    def __init__(self):
        self.apt_cache = MockAptCache()
        

class AutoRemovalPluginTests(unittest.TestCase):

    def setUp(self):
        self.app = MockApplication()
        self.plugin = autoremoval_plugin.AutoRemovablePlugin()
        self.plugin.set_application(self.app)

    def testFindsTheRightCruft(self):
        self.app.apt_cache.add("foo", True)
        self.app.apt_cache.add("bar", True)
        self.app.apt_cache.add("foobar", False)
        names = [cruft.get_name() for cruft in self.plugin.get_cruft()]
        self.assertEqual(sorted(names), sorted(["deb:foo", "deb:bar"]))
