#!/usr/bin/python

from gi.repository import Gtk, GLib

import mock
import os
import subprocess
import unittest

CURDIR = os.path.dirname(os.path.abspath(__file__))


class TestDistroEndOfLife(unittest.TestCase):

    # we need to test two cases:
    # - the current distro is end of life
    # - the next release (the upgrade target) is end of life

    def test_distro_current_distro_end_of_life(self):
        """ this code tests that check-new-release-gtk shows a
            dist-no-longer-supported dialog when it detects that the
            running distribution is no longer supported
        """
        def _nag_dialog_close_helper(checker):
            # this helper is called to verify that the nag dialog appears
            # and that it
            dialog = getattr(checker, "no_longer_supported_nag", None)
            self.assertNotEqual(dialog, None)
            checker.close()
            self.dialog_called = True
        # ----
        try:
            from check_new_release_gtk import CheckNewReleaseGtk
        except ImportError:
            # This may fail in python2, since the Gtk bits needed only exist
            # in update-manager's python3-only code
            return
        options = mock.Mock()
        options.datadir = CURDIR + "/../data"
        options.test_uri = None
        checker = CheckNewReleaseGtk(options)
        meta_release = mock.Mock()
        # pretend the current distro is no longer supported
        meta_release.no_longer_supported = subprocess.Popen(
            ["lsb_release", "-c", "-s"],
            stdout=subprocess.PIPE,
            universal_newlines=True).communicate()[0].strip()
        meta_release.flavor_name = "Ubuntu"
        meta_release.current_dist_version = "0.0"
        # build new release mock
        new_dist = mock.Mock()
        new_dist.name = "zaphod"
        new_dist.version = "127.0"
        new_dist.supported = True
        new_dist.releaseNotesHtmlUri = "http://www.ubuntu.com/html"
        new_dist.releaseNotesURI = "http://www.ubuntu.com/text"
        meta_release.upgradable_to = new_dist
        # schedule a close event in 1 s
        GLib.timeout_add_seconds(1, _nag_dialog_close_helper, checker)
        # run the dialog, this will also run a gtk mainloop so that the
        # timeout works
        self.dialog_called = False
        checker.new_dist_available(meta_release, new_dist)
        self.assertTrue(self.dialog_called, True)

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
