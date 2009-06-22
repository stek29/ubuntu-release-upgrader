# abstract backend that is based around ssh login

from UpgradeTestBackend import UpgradeTestBackend
from DistUpgrade.DistUpgradeConfigParser import DistUpgradeConfig
from DistUpgrade.sourceslist import SourcesList

import ConfigParser
import subprocess
import os
import sys
import os.path
import shutil
import glob
import time
import signal
import signal
import crypt
import tempfile
import copy



class UpgradeTestBackendSSH(UpgradeTestBackend):
    " abstract backend that works with ssh "

    def __init__(self, profile):
        UpgradeTestBackend.__init__(self, profile)
        self.profiledir = os.path.dirname(profile)
        # get ssh key name
        self.ssh_key = os.path.abspath(
            self.config.getWithDefault(
                "NonInteractive",
                "SSHKey",
                "/var/cache/auto-upgrade-tester/ssh-key")
            )
        if not os.path.exists(self.ssh_key):
            print "Creating key: %s" % self.ssh_key
            subprocess.call(["ssh-keygen","-N","","-f",self.ssh_key])

    def login(self):
        " run a shell in the image "
        print "login"
        self.start()
        ret = self._runInImage(["/bin/sh"])
        self.stop()

    def _copyToImage(self, fromF, toF, recursive=False):
        "copy a file (or a list of files) to the given toF image location"
        cmd = ["scp",
               "-P",self.ssh_port,
               "-q","-q", # shut it up
               "-i",self.ssh_key,
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=%s" % os.path.dirname(
                self.profile)+"/known_hosts"
               ]
        if recursive:
            cmd.append("-r")
        # we support both single files and lists of files
        if isinstance(fromF,list):
            cmd += fromF
        else:
            cmd.append(fromF)
        cmd.append("root@localhost:%s" %  toF)
        #print cmd
        ret = subprocess.call(cmd)
        return ret

    def _copyFromImage(self, fromF, toF):
        "copy a file from the given fromF image location"
        cmd = ["scp",
               "-P",self.ssh_port,
               "-q","-q", # shut it up
               "-i",self.ssh_key,
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
               "root@localhost:%s" %  fromF,
               toF
               ]
        #print cmd
        ret = subprocess.call(cmd)
        return ret


    def _runInImage(self, command, **kwargs):
        "run a given command in the image"
        # ssh -l root -p 54321 localhost -i profile/server/ssh_key
        #     -o StrictHostKeyChecking=no
        ret = subprocess.call(["ssh",
#                               "-tt",
                               "-l","root",
                               "-p",self.ssh_port,
                               "localhost",
                               "-q","-q", # shut it up
                               "-i",self.ssh_key,
                               "-o", "StrictHostKeyChecking=no",
                               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
                               ]+command, **kwargs)
        return ret


    def installPackages(self, pkgs):
        " install additional pkgs (list) into the vm before the ugprade "
        if not pkgs:
            return True
        self.start()
        self._runInImage(["apt-get","update"])
        ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "--reinstall", "-y"]+pkgs)
        self.stop()
        return (ret == 0)

