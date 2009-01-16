# ec2 backend

from UpgradeTestBackend import UpgradeTestBackend
from DistUpgradeConfigParser import DistUpgradeConfig

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

from subprocess import Popen, PIPE
from sourceslist import SourcesList

# images created with EC2

class NoCredentialsFoundException(Exception):
    pass


# Step to perform for a ec2 upgrade test
#
# 1. ec2-run-instances $ami-base-instance-name -k ec2-keypair.pem
# 2. get instance public name
# 3. ssh -i ./ec2-keypair.pem root@<public-name> to communicate

class UpgradeTestBackendEC2(UpgradeTestBackend):
    " EC2 backend "

    def __init__(self, profile, basedir):
        UpgradeTestBackend.__init__(self, profile, basedir)
        self.profiledir = os.path.abspath(os.path.dirname(profile))
        # ami base name (e.g .ami-44bb5c2d)
        self.ec2ami = self.config.get("EC2","AMI")
        self.ssh_key = self.config.get("EC2","SSHKey")
        if self.ssh_key.startswith("./"):
            self.ssh_key = self.profiledir + self.ssh_key[1:]
        self.ssh_port = "22"
        # the public name of the instance, e.g. 
        #  ec2-174-129-152-83.compute-1.amazonaws.com
        self.ec2hostname = ""
        # the instance name (e.g. i-3325ad4)
        self.ec2instance = ""
        # get the tools
        self.api_tools_path = self.config.get("EC2","ApiToolsPath")
        if  self.api_tools_path.startswith("./"):
            self.api_tools_path = self.profiledir + self.api_tools_path[1:]
        os.environ["PATH"] = "%s:%s" % (self.api_tools_path, os.environ["PATH"])
        self.ec2_run_instances = "%s/ec2-run-instances" % self.api_tools_path
        self.ec2_describe_instances = "%s/ec2-describe-instances" % self.api_tools_path
        self.ec2_reboot_instances = "%s/ec2-reboot-instances" % self.api_tools_path
        self.ec2_terminate_instances = "%s/ec2-terminate-instances" % self.api_tools_path
        # verify the environemnt
        if not ("EC2_CERT" in os.environ and "EC2_PRIVATE_KEY" in os.environ):
            raise NoCredentialsFoundException("Need EC2_CERT and EC2_PRIVATE_KEY in environment")

    def _copyToImage(self, fromF, toF):
        cmd = ["scp",
               "-P",self.ssh_port,
               "-q","-q", # shut it up
               "-i",self.ssh_key,
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts"]
        # we support both single files and lists of files
        if isinstance(fromF,list):
            cmd += fromF
        else:
            cmd.append(fromF)
        cmd.append("root@%s:%s" %  (self.ec2hostname, toF))
        #print cmd
        ret = subprocess.call(cmd)
        return ret

    def _copyFromImage(self, fromF, toF):
        cmd = ["scp",
               "-P",self.ssh_port,
               "-q","-q", # shut it up
               "-i",self.ssh_key,
               "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
               "root@%s:%s" %  (self.ec2hostname,fromF),
               toF
               ]
        #print cmd
        ret = subprocess.call(cmd)
        return ret


    def _runInImage(self, command, **kwargs):
        ret = subprocess.call(["ssh",
                               "-tt",
                               "-l","root",
                               "-p",self.ssh_port,
                               self.ec2hostname,
                               "-q","-q", # shut it up
                               "-i",self.ssh_key,
                               "-o", "StrictHostKeyChecking=no",
                               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
                               ]+command, **kwargs)
        return ret


    def installPackages(self, pkgs):
        " install additional pkgs (list) into the vm before the ugprade "
        self._runInImage(["apt-get","update"])
        ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "--reinstall", "-y"]+pkgs)
        return (ret == 0)

    def bootstrap(self, force=False):
        print "bootstrap()"

        print "Building new image based on '%s'" % self.ec2ami

        # get common vars
        basepkg = self.config.get("NonInteractive","BasePkg")

        # start the VM
        self.start_instance()

        # install some useful stuff
        ret = self._runInImage(["apt-get","update"])
        assert(ret == 0)
        # FIXME: instead of this retrying (for network errors with 
        #        proxies) we should have a self._runAptInImage() 
        for i in range(3):
            ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",basepkg])
        assert(ret == 0)

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install","--reinstall","-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
                print "apt returned a error, stopping"
                self.stop_instance()
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            print "have PostBootstrapScript: %s" % script
            if os.path.exists(script):
                self._runInImage(["mkdir","/upgrade-tester"])
                self._copyToImage(script, "/upgrade-tester")
                print "running script: %s" % os.path.join("/tmp",script)
                self._runInImage([os.path.join("/upgrade-tester",script)])
            else:
                print "WARNING: %s not found" % script

        if self.config.getWithDefault("NonInteractive",
                                      "UpgradeFromDistOnBootstrap", False):
            print "running apt-get upgrade in from dist (after bootstrap)"
            for i in range(3):
                ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","-y","dist-upgrade"])
            assert(ret == 0)

        print "Cleaning image"
        ret = self._runInImage(["apt-get","clean"])
        assert(ret == 0)

        # done with the bootstrap
        self.reboot_instance()

        # FIXME: support for caching/snapshoting the base image here
        
        return True

    def start_instance(self):
        print "Starting ec2 instance and wait until its availabe "

        # ec2-run-instances self.ec2ami -k self.ssh_key[:-4]

        # start the instance
        # FIXME: get the instance ID here so that we know what
        #        to look for in ec2-describe-instances
        subprocess.call([self.ec2_run_instances, self.ec2ami,
                         "-k",os.path.basename(self.ssh_key[:-4])])


        # now spin until it has a IP adress
        for i in range(900):
            time.sleep(1)
            p = Popen(self.ec2_describe_instances, stdout=PIPE)
            output = p.communicate()[0]
            print output
            for line in output.split("\n"):
                if not line.startswith("INSTANCE"):
                    continue
                try:
                    (keyword, instance, ami, external_ip, internal_ip, status, keypair, number, type, rtime, location, aki, ari) = line.strip().split()
                    if status != "running":
                        print "instance not in state running"
                        continue
                except Exception, e:
                    print e
                    continue
                self.ec2hostname = external_ip
                self.ec2instance = instance
            # check if we got something
            if self.ec2hostname and self.ec2instance:
                break

        # now sping until ssh comes up in the instance
        for i in range(900):
            time.sleep(1)
            if self._runInImage(["/bin/true"]) == 0:
                print "instance available via ssh ping"
                break
        else:
            print "Could not connect to instance after 900s, exiting"
            return False
        return True
    
    def reboot_instance(self):
        " reboot a ec2 instance and wait until its available again "
        # ec2-reboot-instance i-3a870237
        #  does that get a new IP? I guess not 
        res = subprocess.call([self.ec2_reboot_instances,self.ec2instance])
        # FIMXE: find a better way to know when the instance is 
        #        down - maybe with "-v" ?
        time.sleep(5)
        while True:
            if self._runInImage(["/bin/true"]) == 0:
                print "instance rebootet"
                break

    def stop_instance(self):
        " permanently stop a instance (it can never be started again "
        # ec2-terminate-instances i-3a870237
        # terminates are final - all data is lost
        res = subprocess.call([self.ec2_terminate_instances,self.ec2instance])
        # wait until its down
        while True:
            if self._runInImage(["/bin/true"]) != 0:
                print "instance stopped"
                break

    def upgrade(self):
        print "upgrade()"
        upgrader_args = ""
        upgrader_env = ""

        # clean from any leftover pyc files
        for f in glob.glob(self.basefilesdir+"/DistUpgrade/*.pyc"):
            os.unlink(f)

        print "Starting for upgrade"

        assert(self.ec2instance)
        assert(self.ec2hostname)

        print "copy upgrader into image"
        # copy the upgrade into target+/upgrader-tester/
        files = []
        self._runInImage(["mkdir","/upgrade-tester"])
        for f in glob.glob("%s/DistUpgrade/*" % self.basefilesdir):
            if not os.path.isdir(f):
                files.append(f)
        self._copyToImage(files, "/upgrade-tester")
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to image " % self.profile
            self._copyToImage(self.profile, "/upgrade-tester")
        # and any other cfg files
        for f in glob.glob(os.path.dirname(self.profile)+"/*.cfg"):
            if os.path.isfile(f):
                print "Copying '%s' to image " % f
                self._copyToImage(f, "/upgrade-tester")
        # and prereq lists
        prereq = self.config.getWithDefault("PreRequists","SourcesList",None)
        if prereq is not None:
            prereq = os.path.join(os.path.dirname(self.profile),prereq)
            print "Copying '%s' to image" % prereq
            self._copyToImage(prereq, "/upgrade-tester")

        # this is to support direct copying of backport udebs into the 
        # qemu image - useful for testing backports without having to
        # push them into the archive
        backports = self.config.getlist("NonInteractive", "PreRequistsFiles")
        if backports:
            self._runInImage(["mkdir -p /upgrade-tester/backports"])
            for f in backports:
                print "Copying %s" % os.path.basename(f)
                self._copyToImage(f, "/upgrade-tester/backports/")
                self._runInImage(["(cd /upgrade-tester/backports ; dpkg-deb -x %s . )" % os.path.basename(f)])
            upgrader_args = " --have-prerequists"
            upgrader_env = "LD_LIBRARY_PATH=/upgrade-tester/backports/usr/lib PATH=/upgrade-tester/backports/usr/bin:$PATH PYTHONPATH=/upgrade-tester/backports//usr/lib/python$(python -c 'import sys; print \"%s.%s\" % (sys.version_info[0], sys.version_info[1])')/site-packages/ "

        # copy test repo sources.list (if available)
        test_repo = self.config.getWithDefault("NonInteractive","AddRepo","")
        if test_repo:
            test_repo = os.path.join(os.path.dirname(self.profile), test_repo)
            self._copyToImage(test_repo, "/etc/apt/sources.list.d")
            sources = SourcesList(matcherPath=".")
            sources.load(test_repo)
            # add the uri to the list of valid mirros in the image
            for entry in sources.list:
                if (not (entry.invalid or entry.disabled) and
                    entry.type == "deb"):
                    print "adding %s to mirrors" % entry.uri
                    self._runInImage(["echo '%s' >> /upgrade-tester/mirrors.cfg" % entry.uri])

        # start the upgrader
        print "running the upgrader now"
        ret = self._runInImage(["(cd /upgrade-tester/ ; "
                                "%s./dist-upgrade.py %s)" % (upgrader_env, upgrader_args)])
        print "dist-upgrade.py returned: %i" % ret

        # copy the result
        print "coyping the result"
        self._copyFromImage("/var/log/dist-upgrade/*",self.resultdir)

        # stop the machine
        print "Shuting down the VM"
        self.stop_instance()

        return True

    def test(self):
        # FIXME: add some tests here to see if the upgrade worked
        # this should include:
        # - new kernel is runing (run uname -r in target)
        # - did it sucessfully rebootet
        # - is X runing
        # - generate diff of upgrade vs fresh install
        # ...
        return True
        

    
