'''apport package hook for update-manager

(c) 2011 Canonical Ltd.
Author: Brian Murray <brian@ubuntu.com>
'''

import re
from apport.hookutils import (
    attach_gsettings_package, attach_root_command_outputs,
    attach_file_if_exists, recent_syslog)


def add_info(report, ui):

    attach_gsettings_package(report, 'update-manager')
    response = ui.yesno("Is the issue you are reporting one you encountered when upgrading Ubuntu from one release to another?")
    if response:
        report.setdefault('Tags', 'dist-upgrade')
        report['Tags'] += ' dist-upgrade'
        attach_root_command_outputs(report,
            {'VarLogDistupgradeAptclonesystemstatetargz': 'cat /var/log/dist-upgrade/apt-clone_system_state.tar.gz',
             'VarLogDistupgradeAptlog': 'cat /var/log/dist-upgrade/apt.log',
             'VarLogDistupgradeApttermlog': 'cat /var/log/dist-upgrade/apt-term.log',
             'VarLogDistupgradeHistorylog': 'cat /var/log/dist-upgrade/history.log',
             'VarLogDistupgradeLspcitxt': 'cat /var/log/dist-upgrade/lspci.txt',
             'VarLogDistupgradeMainlog': 'cat /var/log/dist-upgrade/main.log',
             'VarLogDistupgradeSystemstatetargz': 'cat /var/log/dist-upgrade/system_state.tar.gz',
             'VarLogDistupgradeTermlog': 'cat /var/log/dist-upgrade/term.log'})
    elif response is None or response is False:
        attach_file_if_exists(report, '/var/log/apt/history.log',
            'DpkgHistoryLog.txt')
        attach_root_command_outputs(report,
            {'DpkgTerminalLog.txt': 'cat /var/log/apt/term.log',
             'CurrentDmesg.txt': 'dmesg | comm -13 --nocheck-order /var/log/dmesg -'})
        report["Aptdaemon"] = recent_syslog(re.compile("AptDaemon"))
