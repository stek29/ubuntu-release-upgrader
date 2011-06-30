'''apport package hook for update-manager

(c) 2011 Canonical Ltd.
Author: Brian Murray <brian@ubuntu.com>
'''

from apport.hookutils import *


def add_info(report):

    # collect gconf settings for update-manager
    report['GconfUpdateManager'] = command_output(['gconftool-2', '-R',
        '/apps/update-manager'])
    attach_file_if_exists(report, '/var/log/apt/history.log',
        'DpkgHistoryLog.txt')
    attach_root_command_outputs(report,
        {'DpkgTerminalLog.txt': 'cat /var/log/apt/term.log',
         'CurrentDmesg.txt': 'dmesg | comm -13 --nocheck-order /var/log/dmesg -'})
