# fstab_plugin_tests.py - unit tests for fstab_plugin.py
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


import os
import tempfile
import unittest

import fstab

import fstab_plugin


class FstabPluginTests(unittest.TestCase):

    fstab_contents = """\
/dev/hda1 /foo ext2 errors=remount-ro 0 1
/dev/hda2 /bar ext3 defaults 0 2
/dev/hda3 /yo ext3 relatime 0 2
/dev/hda3 /yay ext3 noatime 0 2
remote:/foobar /foobar nfs auto 0 0
"""

    def setUp(self):
        self.plugin = fstab_plugin.FstabPlugin()

        fd, self.plugin.fstab_filename = tempfile.mkstemp()
        os.write(fd, self.fstab_contents)
        os.close(fd)

        self.cruft = self.plugin.get_cruft()    
        for cruft in self.cruft:
            cruft.cleanup()
        self.plugin.post_cleanup()
        
        self.fstab = fstab.Fstab()
        self.fstab.read(self.plugin.fstab_filename)

    def find(self, dir):
        for line in self.fstab.lines:
            if line.directory == dir:
                return line
        raise Exception("Not found in fstab: %s" % dir)

    def testAddsRelatimeToExt2Filesystem(self):
        line = self.find("/foo")
        self.assertEqual(set(line.options), 
                         set(["relatime", "errors=remount-ro"]))

    def testAddsRelatimeToExt3Filesystem(self):
        line = self.find("/bar")
        self.assertEqual(set(line.options), 
                         set(["relatime", "defaults"]))

    def testDoesNotAddSecondRelatimeToLineWithItAlready(self):
        line = self.find("/yo")
        self.assertEqual(line.options, ["relatime"])

    def testDoesNotAddRelatimeToLineWithNoatime(self):
        line = self.find("/yay")
        self.assertEqual(line.options, ["noatime"])

    def testDoesNotAddRelatimeToNfsMount(self):
        line = self.find("/foobar")
        self.assertEqual(line.options, ["auto"])

    def testReturnsCruft(self):
        self.assertNotEqual(self.cruft, [])
        
    def testReturnsAllRelatimeCruft(self):
        for cruft in self.cruft:
            self.assert_(isinstance(cruft, fstab_plugin.RelatimeCruft))

    def testReturnsCruftWithCorrectPrefix(self):
        for cruft in self.cruft:
            self.assertEqual(cruft.get_prefix(), "relatime")

    def testReturnsCruftWithCorrectPrefixDescription(self):
        for cruft in self.cruft:
            self.assertEqual(cruft.get_prefix_description(), 
                             "fstab mount option relatime missing")

    def testReturnsCruftWithCorrectShortname(self):
        for cruft in self.cruft:
            self.assert_(cruft.get_shortname() in ["/foo", "/bar"])

    def testReturnsCruftForExt2FilesystemThatMentionsTheRightDirectory(self):
        self.assert_("/foo" in self.cruft[0].get_description())

    def testReturnsCruftForExt3FilesystemThatMentionsTheRightDirectory(self):
        self.assert_("/bar" in self.cruft[1].get_description())

    def testFindsNoCruftAfterPostCommit(self):
        self.assertEqual(self.plugin.get_cruft(), [])
