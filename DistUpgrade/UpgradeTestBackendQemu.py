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

# TODO:
# - refactor and move common code to UpgradeTestBackend
# - convert ChrootNonInteractive 
# - benchmark qemu/qemu+kqemu/kvm/chroot
# - write tests (unittest, doctest?)
# - instead of copy the file in upgrade() use -snapshot
# - when 0.9.0 is available use "-no-reboot" and make
#   the scripts reboot, this this will exit qemu
# - offer "test-upgrade" feature on real system, run it
#   as "qemu -hda /dev/hda -snapshot foo -append init=/upgrade-test"
#   (this *should* write the stuff to the snapshot file
# - add a "kvm" mode to the backend (qemu/kvm should have identical
#   command line options
# - setup a ssh daemon in target and use that to run the commands
# - find a better way to know when a install is finished
# - add "runInTarget()" that will write a marker file so that we can
#   re-run a command if it fails the first time (or fails because
#   a fsck was done and reboot needed in the VM etc)
# - start a X session with the gui-upgrader in a special
#   "non-interactive" mode to see if the gui upgrade would work too


class UpgradeTestBackendQemu(UpgradeTestBackend):
    " very hacky qemu backend - need qemu >= 0.9.0"

    # FIXME: make this part of the config file
    qemu_binary = "qemu"
    qemu_binary = "kvm"
    
    qemu_options = [
        "-m","512",      # memory to use
        "-localtime",
        "-vnc","localhost:0",
        "-redir","tcp:54321::22", # ssh login possible (localhost 54321) available
        "-no-reboot",    # exit on reboot
#        "-no-kvm",      # crashes sometimes with kvm HW
        ]

    def __init__(self, profile, basedir):
        UpgradeTestBackend.__init__(self, profile, basedir)
        self.qemu_pid = None
        self.ssh_key = os.path.dirname(profile)+"/ssh-key"
        # setup mount dir/imagefile location
        tmpdir = self.config.getWithDefault("NonInteractive","Tempdir",None)
        if tmpdir is None:
            tmpdir = tempfile.mkdtemp()
        self.image = os.path.join(tmpdir,"qemu-upgrade-test.image")
        self.target = os.path.join(tmpdir, "qemu-upgrade-test")
        if not os.path.exists(self.target):
            os.makedirs(self.target)

    def _getEnvWithProxy(self):
        env = copy.copy(os.environ)
        try:
            env["http_proxy"] = self.config.get("NonInteractive","Proxy")
        except ConfigParser.NoOptionError:
            pass
        return env
        
    def _runAptInTarget(self, command, cmd_options=[]):
        ret = subprocess.call(["chroot", self.target,
                              "/usr/bin/apt-get",
                              command]+ self.apt_options + cmd_options,
                              env=self._getEnvWithProxy())
        return ret

    def _getProxyLine(self):
        if self.config.has_option("NonInteractive","Proxy"):
            return "export http_proxy=%s" % self.config.get("NonInteractive","Proxy")
        return ""

    def _copyToImage(self, fromF, toF):
        ret = subprocess.call(["scp",
                               "-P","54321",
                               "-q","-q", # shut it up
                               "-i",self.ssh_key,
                               "-o", "StrictHostKeyChecking=no",
                               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
                               fromF,
                               "root@localhost:%s" %  toF,
                               ])
        return ret

    def _runInImage(self, command):
        # ssh -l root -p 54321 localhost -i profile/server/ssh_key
        #     -o StrictHostKeyChecking=no
        ret = subprocess.call(["ssh",
                               "-l","root",
                               "-p","54321",
                               "localhost",
                               "-q","-q", # shut it up
                               "-i",self.ssh_key,
                               "-o", "StrictHostKeyChecking=no",
                               "-o", "UserKnownHostsFile=%s" % os.path.dirname(self.profile)+"/known_hosts",
                               ]+command,
                              env=self._getEnvWithProxy())
        return ret

    def bootstrap(self):
        mirror = self.config.get("NonInteractive","Mirror")
        basepkg = self.config.get("NonInteractive","BasePkg")
        size = int(self.config.getWithDefault("NonInteractive","ImageSize","4000"))
        
        arch = "i386"

        if not os.path.exists(self.target):
            os.mkdir(self.target)
        # make sure we have nothing mounted left
        subprocess.call(["umount",self.target])
        # create image
        # FIXME: - make a proper parition table to get grub installed
        #        - create swap (use hdb for that)
        res = subprocess.call(["qemu-img", "create", self.image, "%sM" % size])
        assert(res == 0)
        # make fs
        res = subprocess.call(["mkfs.ext2","-F",self.image])
        assert(res == 0)
        # now mount it
        res = subprocess.call(["mount","-o","loop,rw",self.image, self.target])
        assert(res == 0)
        # FIXME: what we *really* want here is a d-i install with
        #        proper pre-seeding, but debootstrap will have to do for now
        #        best from a netboot install so that we do not have to
        #        do anthing here 
        res = subprocess.call(["debootstrap", "--arch", arch, self.fromDist, self.target, mirror], env=self._getEnvWithProxy())
        assert(res == 0)
        
        # copy the stuff from toChroot/
        os.chdir("toChroot/")
        for (dirpath, dirnames, filenames) in os.walk("."):
            for name in filenames:
                if not os.path.exists(os.path.join(self.target,dirpath,name)):
                    print "Copying '%s' to chroot" % os.path.join(self.target,dirpath,name)
                    shutil.copy(os.path.join(dirpath,name), os.path.join(self.target,dirpath,name))
        os.chdir("..")

        # setup fstab
        open(self.target+"/etc/fstab","w").write("""
proc /proc proc defaults 0 0
/dev/hda / ext3 defaults,errors=remount-ro 0 0
""")
        # modify /etc/network/interfaces
        # qemu is friendly and give us a network connection,
        # we get IP 10.0.2.15 from the DHCP, the host computer
        # gets IP 10.0.2.2 (DNS 10.0.2.3)
        open(self.target+"/etc/hosts","w").write("""
127.0.0.1 localhost.localdomain localhost
""")
        open(self.target+"/etc/network/interfaces","w").write("""
auto lo eth0
iface lo inet loopback
iface eth0 inet dhcp
""")
        # add proxy and settings
        open(self.target+"/etc/profile","a").write("""
%s
export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
""" % self._getProxyLine())

        # generate ssh keypair with empty passphrase
        if not os.path.exists(self.ssh_key):
            # *sigh* can't use subprocess.call() here, its too clever
            # and strips away the "" after the -N
            #print 'ssh-keygen -q -f %s -N ""' % self.ssh_key
            ret = os.system('ssh-keygen -q -f %s -N ""' % self.ssh_key)
            assert(ret==0)
        os.mkdir(self.target+"/root/.ssh")
        shutil.copy(self.ssh_key+".pub", self.target+"/root/.ssh/authorized_keys")
        
        # FIXME: - what we really want here is to download a kernel-image
        #          to some dir, boot from the dir and run the install
        #          of a new image inside the bootstraped dir (+run grub)
        #        - install grub/lilo/... as well
        res = self._runAptInTarget("clean")
        assert(res == 0)
        res = self._runAptInTarget("install", ["linux-image-generic"])
        assert(res == 0)
        # openssh-server does fail in invoke-rc.d, ignore for now
        res = self._runAptInTarget("install", ["openssh-server"])
        os.mkdir(self.target+"/upgrade-tester")
        # write the first-boot script
#        first_boot=target+"/upgrade-tester/first-boot"
        # FIXME: this below is all wrong, it should work like this:
        #        install first_boot script that installs/sets up
        #        ssh-server for root login with ssh keys
        #        and from that point on use it to run all other
        #        commands (provide runInTarget())
        # 
        # FIXME: - install NonInteractive/BasePkg
        #        - make sure the thing re-tries, with proxies
        #          a read quite often fails (that we run the install twice)
#        open(first_boot,"w").write("""
#!/bin/sh
#LOG=/var/log/dist-upgrade/first-boot.log
#
# proxy (if required)
#%s
#
#mkdir /var/log/dist-upgrade
#apt-get update > $LOG
#apt-get install -y python-apt >> $LOG
#apt-get install -y grub >> $LOG
#apt-get install -y %s >> $LOG
#apt-get install -y %s >> $LOG
#
#reboot
#""" % (self._getProxyLine(), basepkg, basepkg))
#        os.chmod(first_boot, 0755)
#
#        # run the first-boot script
#        open(target+"/etc/rc.local","w").write("""
#/upgrade-tester/first-boot
#""")


        # we do not really need this at this point, use d-i with
        # pre-seeding instead, this solves the same problem nicely.
        # 
        # install a partition table (taken from qemu-make-debian-root
        # install it in front of the ext2 image
        #HEADS=16
        #SECTORS=63
        # 512 bytes in a sector: cancel the 512 with one of the 1024s...
        #CYLINDERS=(( size * 1024 * 2 / (HEADS * SECTORS) ))
        #ret = subprocess.call(["dd","if=/dev/zero","of=%s" % image,
        #                       "bs=512", "count=2"])
        #assert(ret == 0)
        #ret = subprocess.call(["dd","if=%s" % image,"of=%s" % image,
        #                       "seek=2", "bs=512"])
        #assert(ret == 0)
        # install a bootsector
        #res = subprocess.call(["install-mbr","-f",image])
        #assert(res == 0)
        #cmd="echo '63,' | sfdisk -uS -H%s -S%s -C%s %s" % (HEADS, SECTORS, CYLINDERS, image)
        #subprocess.call(cmd, shell=True)
        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)

        subprocess.call(["sync"])
        subprocess.call(["umount", self.target])
        subprocess.call(["e2fsck", "-p", "-f", "-v", self.image])
        # FIXME: find a way to figure if the bootstrap was a success
        subprocess.call(["umount", self.target])
        res = subprocess.call(["mount","-o","loop,ro",self.image, self.target])
        assert(res == 0)
        # now start it
        self.start()

        # FIXME: setup proxy
        pass

        # setup root pw
        print "adding user 'test' to virtual machine"
        ret = self._runInImage(["useradd","-p",crypt.crypt("test","sa"),"test"])
        assert(ret == 0)

        # install some useful stuff (and set DEBIAN_FRONTEND and
        # debconf priority)
        ret = self._runInImage(["apt-get","update"])
        assert(ret == 0)
        ret = self._runInImage(["APT_LISTCHANGES=none","DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",basepkg])
        assert(ret == 0)

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runInImage(["apt-get","install","-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            if os.path.exists(script):
                self._copyToImage(script, "/tmp")
                self._runInImage([os.path.join("/tmp",script)])
            else:
                print "WARNING: %s not found" % script

        print "Cleaning image"
        ret = self._runInImage(["apt-get","clean"])
        assert(ret == 0)
        return True

    def start(self):
        if self.qemu_pid != None:
            return True
        subprocess.call(["umount", self.target])
        res = subprocess.call(["mount","-o","loop,ro", self.image, self.target])
        assert(res == 0)
        self.qemu_pid = subprocess.Popen([self.qemu_binary,
                               "-hda", self.image,
                               "-kernel", "%s/boot/vmlinuz" % self.target,
                               "-initrd", "%s/boot/initrd.img" % self.target,
                               "-append", "root=/dev/hda",
                               ]+self.qemu_options)
        
        # spin here until ssh has come up
        # FIXME: not nice, see if there is a better way and add watchdog
        ret = 1
        while ret != 0:
            ret = self._runInImage(["/bin/true"])
        return True

    def stop(self):
        " we stop because we run with -no-reboot"
        # FIXME: consider using killall qemu instead
        if self.qemu_pid:
            self._runInImage(["/sbin/reboot"])
            print "waiting for qemu to shutdown"
            self.qemu_pid.wait()
            self.qemu_pid = None

    def upgrade(self):
        # copy the upgrade into target+/upgrader-tester/
        # modify /etc/rc.local to run 
        #  (cd /dist-upgrader ; ./dist-upgrade.py)

        # stop any runing virtual machine
        self.stop()

        # FIXME: make this more clever
        subprocess.call(["umount",self.target])
        res = subprocess.call(["mount","-o","loop",self.image, self.target])
        assert(res == 0)

        upgrade_tester_dir = os.path.join(self.target,"upgrade-tester")
        for f in glob.glob("%s/*" % self.basefilesdir):
            if not os.path.isdir(f):
                shutil.copy(f, upgrade_tester_dir)
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to '%s' " % (self.profile, upgrade_tester_dir)
            shutil.copy(self.profile, upgrade_tester_dir)
        # clean from any leftover pyc files
        for f in glob.glob(upgrade_tester_dir+"/*.pyc"):
            os.unlink(f)
        # make sure we run the upgrade
#        open(self.target+"/etc/rc.local","w").write("""
##!/bin/sh#
#
#LOG=/var/log/dist-upgrade/out.log#
#
##proxy (if required)
#%s#
#
#mkdir /var/log/dist-upgrade
#(cd /upgrade-tester ; ./dist-upgrade.py >> $LOG)#
#
#touch /upgrade-tester/upgrade-finished
#reboot
#""" % self._getProxyLine())

        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)
        subprocess.call(["umount", self.target])
        res = subprocess.call(["mount","-o","loop,ro",self.image, self.target])
        assert(res == 0)

        print "starting new qemu instance"
        # start qemu
        self.start()

        # start the upgrader
        ret = self._runInImage(["(cd /upgrade-tester/ ; ./dist-upgrade.py; sync)"])
        # FIXME: - do something useful with ret
        #        - reboot and see what things look like

        self.stop()

        subprocess.call(["umount", self.target])
        res = subprocess.call(["mount","-o","loop,ro",self.image, self.target])
        assert(res == 0)

        # copy the result
        for f in glob.glob(self.target+"/var/log/dist-upgrade/*"):
            print "copying result to: ", self.resultdir
            shutil.copy(f, self.resultdir)

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
