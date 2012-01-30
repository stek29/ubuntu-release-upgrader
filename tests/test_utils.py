#!/usr/bin/python


import logging
import glob
import sys
import unittest

sys.path.insert(0, "../")
from UpdateManager.Core.utils import (is_child_of_process_name, 
                                      get_string_with_no_auth_from_source_entry,
                                      humanize_size,
                                      estimate_kernel_size_in_boot)

class TestUtils(unittest.TestCase):

    def test_humanize_size(self):
        # humanize size is a bit funny, it rounds up to kB as the meaningful
        # unit for users
        self.assertEqual(humanize_size(1000), "1 kB")
        self.assertEqual(humanize_size(10), "1 kB")
        self.assertEqual(humanize_size(1200), "2 kB")
        # but not for MB as well
        self.assertEqual(humanize_size(1200*1000), "1.2 MB")
        self.assertEqual(humanize_size(1478*1000), "1.5 MB")
        # and we don't go to Gb  just yet (as its not really needed
        # in a upgrade context most of the time
        self.assertEqual(humanize_size(1000*1000*1000), "1000.0 MB")

    def test_estimate_kernel_size(self):
        estimate = estimate_kernel_size_in_boot()
        self.assertTrue(estimate > 0)

    def test_is_child_of_process_name(self):
        self.assertTrue(is_child_of_process_name("init"))
        self.assertFalse(is_child_of_process_name("mvo"))
        for e in glob.glob("/proc/[0-9]*"):
            pid = int(e[6:])
            is_child_of_process_name("gdm", pid)
    
    def test_is_port_listening(self):
        from DistUpgrade.utils import is_port_already_listening
        self.assertTrue(is_port_already_listening(22))

    def test_strip_auth_from_source_entry(self):
        from aptsources.sourceslist import SourceEntry
        # entry with PW
        s = SourceEntry("deb http://user:pass@some-ppa/ ubuntu main")
        self.assertTrue(
            not "user" in get_string_with_no_auth_from_source_entry(s))
        self.assertTrue(
            not "pass" in get_string_with_no_auth_from_source_entry(s))
        self.assertEqual(get_string_with_no_auth_from_source_entry(s),
                         "deb http://hidden-u:hidden-p@some-ppa/ ubuntu main")
        # no pw
        s = SourceEntry("deb http://some-ppa/ ubuntu main")
        self.assertEqual(get_string_with_no_auth_from_source_entry(s),
                         "deb http://some-ppa/ ubuntu main")
        

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        logging.basicConfig(level=logging.DEBUG)
    unittest.main()
    
