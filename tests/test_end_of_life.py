#!/usr/bin/python

from gi.repository import Gtk, GLib
from mock import patch

import mock
import os
import subprocess
import unittest

CURDIR = os.path.dirname(os.path.abspath(__file__))


class TestDistroEndOfLife(unittest.TestCase):

    # we need to test two cases:
    # - the current distro is end of life
    # - the next release (the upgrade target) is end of life
    @patch("subprocess.call")
    def test_distro_current_distro_end_of_life(self, mock_call):
        """ this code tests that check-new-release-gtk calls
            update-manager when it detects that the running
            distribution is no longer supported
        """
        def _nag_dialog_close_helper(checker):
            # this helper is called to close the checker
            checker.close()
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
        checker.new_dist_available(meta_release, new_dist)
        mock_call.assert_called_with(['update-manager', '--no-update'])

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
