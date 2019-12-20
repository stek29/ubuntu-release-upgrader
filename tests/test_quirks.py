#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import apt
import apt_pkg
import hashlib
import mock
import os
import unittest
import shutil
import tempfile
import json

from DistUpgrade.DistUpgradeQuirks import DistUpgradeQuirks

CURDIR = os.path.dirname(os.path.abspath(__file__))


class MockController(object):
    def __init__(self):
        self._view = None


class MockConfig(object):
    pass


class MockPopenSnap():
    def __init__(self, cmd, universal_newlines=True,
                 stdout=None):
        self.command = cmd

    def communicate(self):
        snap_name = self.command[2]
        if (snap_name == 'gnome-logs' or
                snap_name == 'gnome-system-monitor'):
            return ["""
name:      test-snap
summary:   Test Snap
publisher: Canonical
license:   unset
description: Some description
commands:
  - gnome-calculator
snap-id:      1234
tracking:     stable/ubuntu-19.04
refresh-date: 2019-04-11
channels:
  stable:    3.32.1  2019-04-10 (406) 4MB -
  candidate: 3.32.2  2019-06-26 (433) 4MB -
  beta:      3.33.89 2019-08-06 (459) 4MB -
  edge:      3.33.90 2019-08-06 (460) 4MB -
installed:   3.32.1             (406) 4MB -
"""]
        else:
            return ["""
name:      test-snap
summary:   Test Snap
publisher: Canonical
license:   unset
description: Some description
commands:
  - gnome-calculator
snap-id:      1234
refresh-date: 2019-04-11
channels:
  stable:    3.32.1  2019-04-10 (406) 4MB -
  candidate: 3.32.2  2019-06-26 (433) 4MB -
  beta:      3.33.89 2019-08-06 (459) 4MB -
  edge:      3.33.90 2019-08-06 (460) 4MB -
"""]


def mock_urlopen_snap(req):
    result = """{{
  "error-list": [],
  "results": [
    {{
      "effective-channel": "stable",
      "instance-key": "test",
      "name": "{name}",
      "released-at": "2019-04-10T18:54:15.717357+00:00",
      "result": "download",
      "snap": {{
        "created-at": "2019-04-09T17:09:29.941588+00:00",
        "download": {{
          "deltas": [],
          "size": {size},
          "url": "SNAPURL"
        }},
        "license": "GPL-3.0+",
        "name": "{name}",
        "prices": {{ }},
        "publisher": {{
          "display-name": "Canonical",
          "id": "canonical",
          "username": "canonical",
          "validation": "verified"
        }},
        "revision": 406,
        "snap-id": "{snap_id}",
        "summary": "GNOME Calculator",
        "title": "GNOME Calculator",
        "type": "app",
        "version": "3.32.1"
      }},
      "snap-id": "{snap_id}"
    }}
  ]
}}
"""
    test_snaps = {
        '1': ("gnome-calculator", 4218880),
        '2': ("test-snap", 2000000)
    }
    json_data = json.loads(req.data)
    snap_id = json_data['actions'][0]['snap-id']
    name = test_snaps[snap_id][0]
    size = test_snaps[snap_id][1]
    response_mock = mock.Mock()
    response_mock.read.return_value = result.format(
        name=name, snap_id=snap_id, size=size)
    return response_mock


def make_mock_pkg(name, is_installed, candidate_rec=""):
    mock_pkg = mock.Mock()
    mock_pkg.name = name
    mock_pkg.is_installed = is_installed
    if candidate_rec:
        mock_pkg.candidate = mock.Mock()
        mock_pkg.candidate.record = candidate_rec
    return mock_pkg


class TestPatches(unittest.TestCase):

    orig_chdir = ''

    def setUp(self):
        # To patch, we need to be in the same directory as the patched files
        self.orig_chdir = os.getcwd()
        os.chdir(CURDIR)

    def tearDown(self):
        os.chdir(self.orig_chdir)

    def _verify_result_checksums(self):
        """ helper for test_patch to verify that we get the expected result """
        # simple case is foo
        patchdir = CURDIR + "/patchdir/"
        with open(patchdir + "foo") as f:
            self.assertFalse("Hello" in f.read())
        with open(patchdir + "foo_orig") as f:
            self.assertTrue("Hello" in f.read())
        md5 = hashlib.md5()
        with open(patchdir + "foo", "rb") as patch:
            md5.update(patch.read())
        self.assertEqual(md5.hexdigest(), "52f83ff6877e42f613bcd2444c22528c")
        # more complex example fstab
        md5 = hashlib.md5()
        with open(patchdir + "fstab", "rb") as patch:
            md5.update(patch.read())
        self.assertEqual(md5.hexdigest(), "c56d2d038afb651920c83106ec8dfd09")
        # most complex example
        md5 = hashlib.md5()
        with open(patchdir + "pycompile", "rb") as patch:
            md5.update(patch.read())
        self.assertEqual(md5.hexdigest(), "97c07a02e5951cf68cb3f86534f6f917")
        # with ".\n"
        md5 = hashlib.md5()
        with open(patchdir + "dotdot", "rb") as patch:
            md5.update(patch.read())
        self.assertEqual(md5.hexdigest(), "cddc4be46bedd91db15ddb9f7ddfa804")
        # test that incorrect md5sum after patching rejects the patch
        with open(patchdir + "fail") as f1, open(patchdir + "fail_orig") as f2:
            self.assertEqual(f1.read(),
                             f2.read())

    def test_patch(self):
        q = DistUpgradeQuirks(MockController(), MockConfig)
        # create patch environment
        patchdir = CURDIR + "/patchdir/"
        shutil.copy(patchdir + "foo_orig", patchdir + "foo")
        shutil.copy(patchdir + "fstab_orig", patchdir + "fstab")
        shutil.copy(patchdir + "pycompile_orig", patchdir + "pycompile")
        shutil.copy(patchdir + "dotdot_orig", patchdir + "dotdot")
        shutil.copy(patchdir + "fail_orig", patchdir + "fail")
        # apply patches
        q._applyPatches(patchdir=patchdir)
        self._verify_result_checksums()
        # now apply patches again and ensure we don't patch twice
        q._applyPatches(patchdir=patchdir)
        self._verify_result_checksums()

    def test_patch_lowlevel(self):
        # test lowlevel too
        from DistUpgrade.DistUpgradePatcher import patch, PatchError
        self.assertRaises(PatchError, patch, CURDIR + "/patchdir/fail",
                          CURDIR + "/patchdir/patchdir_fail."
                          "ed04abbc6ee688ee7908c9dbb4b9e0a2."
                          "deadbeefdeadbeefdeadbeff",
                          "deadbeefdeadbeefdeadbeff")


class TestQuirks(unittest.TestCase):

    orig_recommends = ''
    orig_status = ''

    def setUp(self):
        self.orig_recommends = apt_pkg.config.get("APT::Install-Recommends")
        self.orig_status = apt_pkg.config.get("Dir::state::status")

    def tearDown(self):
        apt_pkg.config.set("APT::Install-Recommends", self.orig_recommends)
        apt_pkg.config.set("Dir::state::status", self.orig_status)

    def test_enable_recommends_during_upgrade(self):
        controller = mock.Mock()

        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        # server mode
        apt_pkg.config.set("APT::Install-Recommends", "0")
        controller.serverMode = True
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        q.ensure_recommends_are_installed_on_desktops()
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        # desktop mode
        apt_pkg.config.set("APT::Install-Recommends", "0")
        controller.serverMode = False
        self.assertFalse(apt_pkg.config.find_b("APT::Install-Recommends"))
        q.ensure_recommends_are_installed_on_desktops()
        self.assertTrue(apt_pkg.config.find_b("APT::Install-Recommends"))

    def test_parse_from_modaliases_header(self):
        pkgrec = {
            "Package": "foo",
            "Modaliases": "modules1(pci:v00001002d00006700sv*sd*bc03sc*i*, "
                          "pci:v00001002d00006701sv*sd*bc03sc*i*), "
                          "module2(pci:v00001002d00006702sv*sd*bc03sc*i*, "
                          "pci:v00001001d00006702sv*sd*bc03sc*i*)"
        }
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        self.assertEqual(q._parse_modaliases_from_pkg_header({}), [])
        self.assertEqual(q._parse_modaliases_from_pkg_header(pkgrec),
                         [("modules1",
                           ["pci:v00001002d00006700sv*sd*bc03sc*i*",
                            "pci:v00001002d00006701sv*sd*bc03sc*i*"]),
                          ("module2",
                           ["pci:v00001002d00006702sv*sd*bc03sc*i*",
                            "pci:v00001001d00006702sv*sd*bc03sc*i*"])])

    def disabled__as_fglrx_is_gone_testFglrx(self):
        mock_lspci_good = set(['1002:9990'])
        mock_lspci_bad = set(['8086:ac56'])
        config = mock.Mock()
        cache = apt.Cache()
        controller = mock.Mock()
        controller.cache = cache
        q = DistUpgradeQuirks(controller, config)
        if q.arch not in ['i386', 'amd64']:
            return self.skipTest("Not on an arch with fglrx package")
        self.assertTrue(q._supportInModaliases("fglrx", mock_lspci_good))
        self.assertFalse(q._supportInModaliases("fglrx", mock_lspci_bad))

    def test_screensaver_poke(self):
        # fake nothing is installed
        empty_status = tempfile.NamedTemporaryFile()
        apt_pkg.config.set("Dir::state::status", empty_status.name)

        # create quirks class
        controller = mock.Mock()
        config = mock.Mock()
        quirks = DistUpgradeQuirks(controller, config)
        quirks._pokeScreensaver()
        res = quirks._stopPokeScreensaver()
        res  # pyflakes

    def test_get_linux_metapackage(self):
        q = DistUpgradeQuirks(mock.Mock(), mock.Mock())
        mock_cache = set([
            make_mock_pkg(
                name="linux-image-3.19-24-generic",
                is_installed=True,
                candidate_rec={"Source": "linux"},
            ),
        ])
        pkgname = q._get_linux_metapackage(mock_cache, headers=False)
        self.assertEqual(pkgname, "linux-generic")

    def test_get_lpae_linux_metapackage(self):
        q = DistUpgradeQuirks(mock.Mock(), mock.Mock())
        mock_cache = set([
            make_mock_pkg(
                name="linux-image-4.2.0-16-generic-lpae",
                is_installed=True,
                candidate_rec={"Source": "linux"},
            ),
        ])
        pkgname = q._get_linux_metapackage(mock_cache, headers=False)
        self.assertEqual(pkgname, "linux-generic-lpae")

    def test_get_lowlatency_linux_metapackage(self):
        q = DistUpgradeQuirks(mock.Mock(), mock.Mock())
        mock_cache = set([
            make_mock_pkg(
                name="linux-image-4.2.0-16-lowlatency",
                is_installed=True,
                candidate_rec={"Source": "linux"},
            ),
        ])
        pkgname = q._get_linux_metapackage(mock_cache, headers=False)
        self.assertEqual(pkgname, "linux-lowlatency")

    def test_get_lts_linux_metapackage(self):
        q = DistUpgradeQuirks(mock.Mock(), mock.Mock())
        mock_cache = set([
            make_mock_pkg(
                name="linux-image-3.13.0-24-generic",
                is_installed=True,
                candidate_rec={"Source": "linux-lts-quantal"},
            ),
        ])
        pkgname = q._get_linux_metapackage(mock_cache, headers=False)
        self.assertEqual(pkgname, "linux-generic-lts-quantal")


class TestSnapQuirks(unittest.TestCase):

    def test_get_from_and_to_version(self):
        # Prepare the state for testing
        controller = mock.Mock()
        controller.fromDist = 'disco'
        controller.toDist = 'eoan'
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        # Call method under test
        q._get_from_and_to_version()
        self.assertEqual(q._from_version, '19.04')
        self.assertEqual(q._to_version, '19.10')

    @mock.patch("subprocess.Popen", MockPopenSnap)
    def test_prepare_snap_replacement_data(self):
        # Prepare the state for testing
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        q._from_version = "19.04"
        q._to_version = "19.10"
        # Call method under test
        q._prepare_snap_replacement_data()
        # Check if the right snaps have been detected as installed and
        # needing refresh and which ones need installation
        self.assertDictEqual(
            q._snap_list,
            {'core18': {
                'command': 'install', 'snap-id': '1234',
                'channel': 'stable'},
             'gnome-3-28-1804': {
                'command': 'install', 'snap-id': '1234',
                'channel': 'stable/ubuntu-19.10'},
             'gtk-common-themes': {
                'command': 'install', 'snap-id': '1234',
                'channel': 'stable/ubuntu-19.10'},
             'gnome-calculator': {
                'command': 'install', 'snap-id': '1234',
                'channel': 'stable/ubuntu-19.10'},
             'gnome-characters': {
                'command': 'install', 'snap-id': '1234',
                'channel': 'stable/ubuntu-19.10'},
             'gnome-logs': {
                'command': 'refresh',
                'channel': 'stable/ubuntu-19.10'}})

    @mock.patch("DistUpgrade.DistUpgradeQuirks.get_arch")
    @mock.patch("urllib.request.urlopen")
    def test_calculate_snap_size_requirements(self, urlopen, arch):
        # Prepare the state for testing
        arch.return_value = 'amd64'
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        # We mock out _prepare_snap_replacement_data(), as this is tested
        # separately.
        q._prepare_snap_replacement_data = mock.Mock()
        q._snap_list = {
            'test-snap': {'command': 'install', 'snap-id': '2',
                          'channel': 'stable/ubuntu-19.10'},
            'gnome-calculator': {'command': 'install', 'snap-id': '1',
                                 'channel': 'stable/ubuntu-19.10'},
            'gnome-system-monitor': {'command': 'refresh',
                                     'channel': 'stable/ubuntu-19.10'}
        }
        q._to_version = "19.10"
        # Mock out urlopen in such a way that we get a mocked response based
        # on the parameters given but also allow us to check call arguments
        # etc.
        urlopen.side_effect = mock_urlopen_snap
        # Call method under test
        q._calculateSnapSizeRequirements()
        # Check if the size was calculated correctly
        self.assertEqual(q.extra_snap_space, 6218880)
        # Check if we only sent queries for the two command: install snaps
        self.assertEqual(urlopen.call_count, 2)
        # Make sure each call had the right headers and parameters
        for call in urlopen.call_args_list:
            req = call[0][0]
            self.assertIn(b"stable/ubuntu-19.10", req.data)
            self.assertDictEqual(
                req.headers,
                {'Snap-device-series': '16',
                 'Content-type': 'application/json',
                 'Snap-device-architecture': 'amd64'})

    @mock.patch("subprocess.run")
    def test_replace_debs_with_snaps(self, run_mock):
        controller = mock.Mock()
        config = mock.Mock()
        q = DistUpgradeQuirks(controller, config)
        q._snap_list = {
            'core18': {'command': 'install', 'snap-id': '1234',
                       'channel': 'stable'},
            'gnome-3-28-1804': {'command': 'install', 'snap-id': '1234',
                                'channel': 'stable/ubuntu-19.10'},
            'gtk-common-themes': {'command': 'install', 'snap-id': '1234',
                                  'channel': 'stable/ubuntu-19.10'},
            'gnome-calculator': {'command': 'install', 'snap-id': '1234',
                                 'channel': 'stable/ubuntu-19.10'},
            'gnome-characters': {'command': 'install', 'snap-id': '1234',
                                 'channel': 'stable/ubuntu-19.10'},
            'gnome-logs': {'command': 'refresh',
                           'channel': 'stable/ubuntu-19.10'},
            'gnome-system-monitor': {'command': 'refresh',
                                     'channel': 'stable/ubuntu-19.10'}
        }
        q._to_version = "19.10"
        q._replaceDebsWithSnaps()
        # Make sure all snaps have been handled
        self.assertEqual(run_mock.call_count, 7)
        snaps_refreshed = {}
        snaps_installed = {}
        # Check if all the snaps that needed to be installed were installed
        # and those that needed a refresh - refreshed
        # At the same time, let's check that all the snaps were acted upon
        # while using the correct channel and branch
        for call in run_mock.call_args_list:
            args = call[0][0]
            if args[1] == 'install':
                snaps_installed[args[4]] = args[3]
            else:
                snaps_refreshed[args[4]] = args[3]
        self.assertDictEqual(
            snaps_refreshed,
            {'gnome-logs': 'stable/ubuntu-19.10',
             'gnome-system-monitor': 'stable/ubuntu-19.10'})
        self.assertDictEqual(
            snaps_installed,
            {'core18': 'stable',
             'gnome-3-28-1804': 'stable/ubuntu-19.10',
             'gtk-common-themes': 'stable/ubuntu-19.10',
             'gnome-calculator': 'stable/ubuntu-19.10',
             'gnome-characters': 'stable/ubuntu-19.10'})
        # Make sure we marked the replaced ones for removal
        # Here we only check if the right number of 'packages' has been
        # added to the forced_obsoletes list - not all of those packages are
        # actual deb packages that will have to be removed during the upgrade
        self.assertEqual(controller.forced_obsoletes.append.call_count, 5)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
