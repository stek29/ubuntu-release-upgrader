'''apport package hook for ubuntu-release-upgrader

(c) 2011 Canonical Ltd.
Author: Brian Murray <brian@ubuntu.com>
'''

import os

from apport.hookutils import (
    attach_gsettings_package,
    attach_file_if_exists,
    attach_root_command_outputs,
    root_command_output)


def add_info(report, ui):
    try:
        attach_gsettings_package(report, 'ubuntu-release-upgrader')
    except:
        pass
    report['CrashDB'] = 'ubuntu'
    report.setdefault('Tags', 'dist-upgrade')
    report['Tags'] += ' dist-upgrade'
    clone_file = '/var/log/dist-upgrade/apt-clone_system_state.tar.gz'
    if os.path.exists(clone_file):
        report['VarLogDistupgradeAptclonesystemstate.tar.gz'] =  \
            root_command_output(["cat", clone_file], decode_utf8=False)
    attach_file_if_exists(report, '/var/log/dist-upgrade/apt.log',
        'VarLogDistupgradeAptlog')
    attach_file_if_exists(report, '/var/log/dist-upgrade/apt-term.log',
        'VarLogDistupgradeApttermlog')
    attach_file_if_exists(report, '/var/log/dist-upgrade/history.log',
        'VarLogDistupgradeAptHistorylog')
    attach_file_if_exists(report, '/var/log/dist-upgrade/lspci.txt',
        'VarLogDistupgradeLspcitxt')
    attach_file_if_exists(report, '/var/log/dist-upgrade/main.log',
        'VarLogDistupgradeMainlog')
    attach_file_if_exists(report, '/var/log/dist-upgrade/term.log',
        'VarLogDistupgradeTermlog')
    attach_file_if_exists(report, '/var/log/dist-upgrade/screenlog.0',
        'VarLogDistupgradeScreenlog')
    attach_root_command_outputs(
        report,
        {'CurrentDmesg.txt':
            'dmesg | comm -13 --nocheck-order /var/log/dmesg -'})
