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
/dev/scd0 /cdrom auto defaults 0 0
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

    def testDoesNotAddRelatimeToLineWithNoatime(self):
        line = self.find("/yay")
        self.assertEqual(line.options, ["noatime"])

    def testDoesNotAddRelatimeToNfsMount(self):
        line = self.find("/foobar")
        self.assertEqual(line.options, ["auto"])

    def testFindsNoCruftAfterPostCommit(self):
        self.assertEqual(self.plugin.get_cruft(), [])


class RelatimeCruftTests(unittest.TestCase):

    def setUp(self):
        self.lines = {}
        self.crufts = {}
        for x in ["ext2", "ext3"]:
            self.lines[x] = fstab.Line("/dev/disk /mnt %s defaults 0 2")
            self.crufts[x] = fstab_plugin.RelatimeCruft(self.lines[x])
            self.crufts[x].cleanup()

    def test_returns_correct_prefix(self):
        self.assertEqual(self.crufts["ext2"].get_prefix(), "relatime")
    
    def test_prefix_description_mentions_relatime(self):
        self.assert_("relatime" in 
                     self.crufts["ext2"].get_prefix_description())

    def test_returns_correct_shortname(self):
        self.assertEqual(self.crufts["ext2"].get_shortname(), "/mnt")
        
    def test_description_contains_mount_point(self):
        self.assert_("/mnt" in self.crufts["ext2"].get_description())

    def test_adds_relatime_to_ext2(self):
        self.assertEqual(set(self.lines["ext2"].options),
                         set(["relatime", "defaults"]))

    def test_adds_relatime_to_ext3(self):
        self.assertEqual(set(self.lines["ext3"].options),
                         set(["relatime", "defaults"]))


# class Scd0CruftTests(unittest.TestCase):

#     def setUp(self):
#         self.line = fstab.Line("/dev/scd0 /cdrom defaults noauto 0 2")
#         self.cruft = fstab_plugin.Scd0Cruft(self.line)
#         self.cruft.cleanup()

#     def test_returns_correct_prefix(self):
#         self.assertEqual(self.cruft.get_prefix(), "scd0")
    
#     def test_prefix_description_mentions_scd0(self):
#         self.assert_("/dev/scd0" in self.cruft.get_prefix_description())
    
#     def test_returns_correct_shortname(self):
#         self.assertEqual(self.cruft.get_shortname(), "/dev/scd0")
        
#     def test_description_contains_old_and_new_device(self):
#         self.assert_("/dev/scd0" in self.cruft.get_description())
#         self.assert_("/dev/cdrom" in self.cruft.get_description())

#     def testRewritesScd0AsCdromDevice(self):
#         self.assertEqual(self.line.device, "/dev/cdrom")
