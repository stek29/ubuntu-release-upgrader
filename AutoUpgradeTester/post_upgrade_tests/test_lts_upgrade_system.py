#!/usr/bin/python
#
# This script checks system-wide configuration settings after an Ubuntu 10.04
# LTS to Ubuntu 12.04 LTS upgrade. Run this after upgrading to 12.04 or later.
# It reads the old gdm settings and ensures that they were appropriately
# migrated to lightdm and that lightdm is the default DM.
# It does not need any particular privileges, it is fine to run this as any
# user.
#
# (C) 2012 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# License: GPL v2 or higher

import unittest
import os, sys
import ConfigParser

class T(unittest.TestCase):
    @classmethod
    def setUpClass(klass):
        # read gdm configuration
        klass.gdm_config = klass._read_conf('/etc/gdm/custom.conf', 'daemon')
        klass.lightdm_config = klass._read_conf('/etc/lightdm/lightdm.conf', 'SeatDefaults')

    def test_lightdm_default_dm(self):
        '''lightdm is the default display manager'''

        with open('/etc/X11/default-display-manager') as f:
            default_dm = f.read().strip()

        self.assertTrue(os.access(default_dm, os.X_OK))
        self.assertEqual(os.path.basename(default_dm), 'lightdm')

    def test_autologin_migration(self):
        '''autologin migration from gdm to lightdm'''

        if self.gdm_config.get('automaticloginenable', 'false') == 'true':
            gdm_autologin = self.gdm_config.get('automaticlogin', '')
        else:
            gdm_autologin = ''

        self.assertEqual(gdm_autologin, self.lightdm_config.get('autologin-user', ''))

    @classmethod
    def _read_conf(klass, filename, section):
        '''Read section from an INI configuration file.

        Return a dictionary with the configuration of the given section.
        '''
        p = ConfigParser.ConfigParser()
        p.read(filename)
        config = {}
        try:
            for (key, value) in p.items(section):
                config[key] = value
        except ConfigParser.NoSectionError:
            # just keep an empty config
            pass
        return config

# Only run on lts-ubuntu testcases
if not os.path.exists('/upgrade-tester/prepare_lts_desktop'):
    print "Not an Ubuntu Desktop LTS upgrade. Skipping!"
    sys.exit(0)

unittest.main()
