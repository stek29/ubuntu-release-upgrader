# dpkg_dotfile_plugin_tests.py - unittests for dpkg_dotfile_plugin.py
# Copyright (C) 2009  Canonical, Ltd.
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
import shutil
import tempfile
import unittest

import dpkg_dotfile_plugin


class DpkgDotfilePluginTests(unittest.TestCase):

    def setUp(self):
        self.plugin = dpkg_dotfile_plugin.DpkgDotfilePlugin()
        
        self.root = tempfile.mkdtemp()
        self.empty = self.makedir("empty")
        self.etc = self.makedir("etc")
        self.subdir = self.makedir("etc/subdir")
        self.dpkg_old = self.create_file(self.etc, "foo.dpkg-old")
        self.dpkg_new = self.create_file(self.subdir, "foo.dpkg-new")
        self.dpkg_dir = self.makedir("etc/subdir.dpkg-old")
        filename = self.create_file(self.etc, "foo")
        self.dpkg_sym = self.create_symlink(filename, 
                                            self.etc, "foobar.dpkg-old")
        self.create_file(self.etc, "foo")
        
    def makedir(self, name):
        path = os.path.join(self.root, name)
        os.mkdir(path)
        return path

    def create_file(self, dirname, basename):
        path = os.path.join(dirname, basename)
        file(path, "w").close()
        return path

    def create_symlink(self, existing, dirname, linkname):
        path = os.path.join(dirname, linkname)
        os.symlink(existing, path)
        return path
        
    def tearDown(self):
        shutil.rmtree(self.root)

    def test_directories_set_to_etc_by_default(self):
        # This test is here so that nobody changes the default list by
        # mistake, without realizing that it is important.
        self.assertEqual(sorted(self.plugin.dirs), 
                         sorted(["/etc",
                                 "/var/ax25",
                                 "/var/cache/roxen4",
                                 "/var/games",
                                 "/var/lib/crafty",
                                 "/var/lib/drac",
                                 "/var/lib/firebird2",
                                 "/var/lib/gnats",
                                 "/var/lib/leksbot",
                                 "/var/lib/linpopup",
                                 "/var/lib/lxr-cvs",
                                 "/var/lib/mason",
                                 "/var/lib/roxen4",
                                 "/var/lib/sysnews",
                                 "/var/list",
                                 "/var/spool/fcron",
                                 "/var/spool/hylafax/bin",
                                 "/var/yp"]))

    def test_scan_finds_both_files_and_nothing_else(self):
        self.assertEqual(sorted(self.plugin.scan(self.etc)),
                         sorted([self.dpkg_old, self.dpkg_new]))

    def test_get_cruft_returns_empty_list_for_empty_directory(self):
        self.plugin.dirs = [self.empty]
        self.assertEqual(self.plugin.get_cruft(), [])

    def mock_scan(self, dirname):
        self.scanned.append(dirname)
        return []

    def test_get_cruft_visits_all_directories(self):
        self.plugin.dirs = [self.empty, self.etc]
        self.plugin.scan = self.mock_scan
        self.scanned = []
        self.plugin.get_cruft()
        self.assertEqual(self.scanned, [self.empty, self.etc])

    def test_get_cruft_returns_the_right_stuff(self):
        self.plugin.dirs = [self.empty, self.etc]
        self.assertEqual(sorted([x.get_shortname() 
                                 for x in self.plugin.get_cruft()]),
                         sorted([self.dpkg_old, self.dpkg_new]))
