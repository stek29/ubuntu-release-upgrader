# qemu backend

from UpgradeTestBackend import UpgradeTestBackend
from DistUpgradeConfigParser import DistUpgradeConfig

import ConfigParser
import subprocess
import os
import os.path
import shutil
import glob
import time
import signal
import signal
import crypt
import tempfile
import copy

# images created with http://bazaar.launchpad.net/~mvo/ubuntu-jeos/mvo
#  ./ubuntu-jeos-builder --vm kvm --kernel-flavor generic --suite feisty --ssh-key `pwd`/ssh-key.pub  --components main,restricted --rootsize 20G
# 


# TODO: 
# - add support to boot certain images with certain parameters
#   (dapper-386 needs qemu/kvm with "-no-acpi" to boot reliable)
# - add option to use pre-done base images
#   the bootstrap() step is then a matter of installing the right
#   packages into the image (via _runInImage())
# 
# - refactor and move common code to UpgradeTestBackend
# - convert ChrootNonInteractive 
# - benchmark qemu/qemu+kqemu/kvm/chroot
# - write tests (unittest, doctest?)
# - offer "test-upgrade" feature on real system, run it
#   as "qemu -hda /dev/hda -snapshot foo -append init=/upgrade-test"
#   (this *should* write the stuff to the snapshot file
# - add "runInTarget()" that will write a marker file so that we can
#   re-run a command if it fails the first time (or fails because
#   a fsck was done and reboot needed in the VM etc)
# - start a X session with the gui-upgrader in a special
#   "non-interactive" mode to see if the gui upgrade would work too

class NoImageFoundException(Exception):
    pass

class PortInUseException(Exception):
    pass


class UpgradeTestBackendQemu(UpgradeTestBackend):
    " qemu/kvm backend - need qemu >= 0.9.0"

    # FIXME: make this part of the config file
    #qemu_binary = "qemu"
    qemu_binary = "kvm"
    
    qemu_options = [
        "-m","1024",      # memory to use
        "-localtime",
        "-vnc","localhost:0",
        "-no-reboot",    # exit on reboot
        "-no-acpi",      # the dapper kernel does not like qemus acpi
#        "-no-kvm",      # crashes sometimes with kvm HW
        ]

    def __init__(self, profile, basedir):
        UpgradeTestBackend.__init__(self, profile, basedir)
        self.qemu_pid = None
        self.profiledir = os.path.dirname(profile)
        # setup mount dir/imagefile location
        self.baseimage = self.config.get("NonInteractive","BaseImage")
        if not os.path.exists(self.baseimage):
            raise NoImageFoundException
        if self.config.getWithDefault("NonInteractive","SwapImage",""):
            self.qemu_options.append("-hdb")
            self.qemu_options.append(self.config.get("NonInteractive","SwapImage"))
        self.image = os.path.join(self.profiledir, "test-image")
        # make ssh login possible (localhost 54321) available
        self.ssh_key = os.path.join(self.profiledir,self.config.getWithDefault("NonInteractive","SSHKey","ssh-key"))
        self.ssh_port = self.config.getWithDefault("NonInteractive","SshPort","54321")
        self.qemu_options.append("-redir")
        self.qemu_options.append("tcp:%s::22" % self.ssh_port)
        # check if the ssh port is in use
        if subprocess.call("netstat -t -l -n |grep 0.0.0.0:%s" % self.ssh_port,
                           shell=True) == 0:
            raise PortInUseException, "the port is already in use (another upgrade tester is running?)"

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
        cmd.append("root@localhost:%s" %  toF)
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
               "root@localhost:%s" %  fromF,
               toF
               ]
        #print cmd
        ret = subprocess.call(cmd)
        return ret


    def _runInImage(self, command, withProxy=True):
        # ssh -l root -p 54321 localhost -i profile/server/ssh_key
        #     -o StrictHostKeyChecking=no
        ret = subprocess.call(["ssh",
                               "-l","root",
                               "-p",self.ssh_port,
                               "localhost",
                               "-q","-q", # shut it up
                               "-i",self.ssh_key,
                               "-o", "StrictHostKeyChecking=no",
                               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
                               ]+command)
        return ret


    def genDiff(self):
        self.config.set("Sources","From",
                        backend.config.get("Sources","To"))
        diff_image = os.path.join(backend.profiledir, "test-image.diff")
        self.baseimage = diff_image
        self.image = diff_image
        self.bootstrap(force=True)

    def bootstrapBaseImage(self):
        " bootstrap the base image using the jeos builder "
        $ ./ubuntu-jeos-builder --vm kvm --kernel-flavor generic --suite feisty --ssh-key `pwd`/ssh-key.pub  --components main,restricted  --rootsize 80G --no-opt

    def bootstrap(self, force=False):
        print "bootstrap()"

        # copy image into place, use baseimage as template
        # we expect to be able to ssh into the baseimage to
        # set it up
        if (not force and
            os.path.exists("%s.%s" % (self.image,self.fromDist)) and 
            self.config.has_option("NonInteractive","CacheBaseImage") and
            self.config.getboolean("NonInteractive","CacheBaseImage")):
            print "Not bootstraping again, we have a cached BaseImage"
            shutil.copy("%s.%s" % (self.image,self.fromDist), self.image)
            return True

        print "Building new image '%s' based on '%s'" % (self.image, self.baseimage)
        if force or not os.path.exists(self.baseimage):
            self._bootstrapBaseImage()
        shutil.copy(self.baseimage, self.image)

        # get common vars
        mirror = self.config.get("NonInteractive","Mirror")
        basepkg = self.config.get("NonInteractive","BasePkg")

        # start the VM
        self.start()

        # FIXME: make this part of the apt env
        #        otherwise we get funny debconf promtps for 
        #        e.g. the xserver
        #export DEBIAN_FRONTEND=noninteractive
        #export APT_LISTCHANGES_FRONTEND=none
        # 

        # generate static network config (NetworkManager likes
        # to reset the dhcp interface and that sucks when
        # going into the VM with ssh)
        nm = self.config.getWithDefault("NonInteractive","WorkaroundNetworkManager","")
        if nm:
            interfaces = tempfile.NamedTemporaryFile()
            interfaces.write("""
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
       address 10.0.2.15
       netmask 255.0.0.0
       gateway 10.0.2.2
""")
            interfaces.flush()
            self._copyToImage(interfaces.name, "/etc/network/interfaces")
        

        # generate apt.conf
        proxy = self.config.getWithDefault("NonInteractive","Proxy","")
        if proxy:
            aptconf = tempfile.NamedTemporaryFile()
            aptconf.write('Acquire::http::proxy "%s";' % proxy)
            aptconf.flush()
            self._copyToImage(aptconf.name, "/etc/apt/apt.conf")

        # tzdata is unhappy without that file
        tzone = tempfile.NamedTemporaryFile()
        tzone.write("Europe/Berlin")
        tzone.flush()
        self._copyToImage(tzone.name, "/etc/timezone")

        # create /etc/apt/sources.list
        sources = self.getSourcesListFile()
        self._copyToImage(sources.name, "/etc/apt/sources.list")

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
            ret= self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install","-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
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
        self.stop()

        # copy cache into place (if needed)
        if (self.config.has_option("NonInteractive","CacheBaseImage") and
            self.config.getboolean("NonInteractive","CacheBaseImage")):
            shutil.copy(self.image, "%s.%s" % (self.image,self.fromDist))
        
        return True

    def start(self):
        print "Starting qemu"
        if self.qemu_pid != None:
            print "already runing"
            return True
        self.qemu_pid = subprocess.Popen([self.qemu_binary,
                                          "-hda", self.image,
                                          ]+self.qemu_options)
        
        # spin here until ssh has come up and we can login
        for i in range(900):
            time.sleep(1)
            if self._runInImage(["/bin/true"]) == 0:
                break
        else:
            print "Could not start image after 300s, exiting"
            return False
        return True

    def stop(self):
        " we stop because we run with -no-reboot"
        # FIXME: add watchdog here too
        #        if the qemu process does not stop in sensible time,
        #        try to umount all FS and then kill it 
        if self.qemu_pid:
            self._runInImage(["/sbin/reboot"])
            print "waiting for qemu to shutdown"
            self.qemu_pid.wait()
            self.qemu_pid = None
            print "qemu stopped"

    def upgrade(self):
        print "upgrade()"

        # clean from any leftover pyc files
        for f in glob.glob(self.basefilesdir+"/DistUpgrade/*.pyc"):
            os.unlink(f)

        print "Starting for upgrade"
        self.start()

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
        prereq = self.config.getWithDefault("PreRequists","SourcesList",None)
        if prereq is not None:
            prereq = os.path.join(os.path.dirname(self.profile),prereq)
            print "Copying '%s' to image" % prereq
            self._copyToImage(prereq, "/upgrade-tester")

        # start the upgrader
        print "running the upgrader now"
        ret = self._runInImage(["(cd /upgrade-tester/ ; ./dist-upgrade.py)"])
        print "dist-upgrade.py returned: %i" % ret

        # copy the result
        print "coyping the result"
        self._copyFromImage("/var/log/dist-upgrade/*",self.resultdir)

        # stop the machine
        print "Shuting down the VM"
        self.stop()

        return True

    def test(self):
        # FIXME: add some tests here to see if the upgrade worked
        # this should include:
        # - new kernel is runing (run uname -r in target)
        # - did it sucessfully rebootet
        # - is X runing
        # ...
        return True
        

if __name__ == "__main__":
    import sys
    
    # FIXME: very rough proof of conecpt, unify with the chroot
    #        and automatic-upgrade code
    # see also /usr/sbin/qemu-make-debian-root
    
    qemu = UpgradeTestBackendQemu(sys.argv[1],".")
    #qemu.bootstrap()
    #qemu.start()
    #qemu._runInImage(["ls","/"])
    #qemu.stop()
    qemu.upgrade()

    # FIXME: now write something into rc.local again and run reboot
    #        and see if we come up with the new kernel
