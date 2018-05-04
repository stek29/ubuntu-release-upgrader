# -*- coding: utf-8; Mode: Python; indent-tabs-mode: nil; tab-width: 4 -*-

# Copyright (C) 2018 Canonical Ltd.
#
# Functions useful for the final install.py script and for ubiquity
# plugins to use
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


import logging
import json
import os
import stat
import subprocess
import time


def get():
    """Return a singleton _Telemetry instance."""
    if _Telemetry._telemetry is None:
        _Telemetry._telemetry = _Telemetry()
    return _Telemetry._telemetry


class _Telemetry():

    _telemetry = None

    def __init__(self):
        self._metrics = {}
        self._stages_hist = {}
        self._start_time = time.time()
        self._metrics["From"] = subprocess.Popen(
            ["lsb_release", "-r", "-s"], stdout=subprocess.PIPE,
            universal_newlines=True).communicate()[0].strip()
        self.add_stage('start')
        self._dest_path = '/var/log/upgrade/telemetry'

    def add_stage(self, stage_name):
        """Record installer stage with current time"""
        self._stages_hist[int(time.time() - self._start_time)] = stage_name

    def set_updater_type(self, updater_type):
        """Record updater type"""
        self._metrics['Type'] = updater_type

    def done(self):
        """Close telemetry collection

        Save to destination file"""

        self._metrics['Stages'] = self._stages_hist

        target_dir = os.path.dirname(self._dest_path)
        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            with open(self._dest_path, 'w') as f:
                json.dump(self._metrics, f)
            os.chmod(self._dest_path,
                     stat.S_IRUSR | stat.S_IWUSR |
                     stat.S_IRGRP | stat.S_IROTH)
        except OSError as e:
            logging.warning("Exception while storing telemetry data: " +
                            str(e))

# vim:ai:et:sts=4:tw=80:sw=4:
