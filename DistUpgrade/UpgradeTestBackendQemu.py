# qemu backend

from UpgradeTestBackend import UpgradeTestBackend
from DistUpgradeConfigParser import DistUpgradeConfig

import subprocess
import os
import os.path
import shutil
import glob
import time
import signal

# TODO:
# - refactor and move common code to UpgradeTestBackend
# - convert ChrootNonInteractive 
# - find a better way to know when a install is finished
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

class UpgradeTestBackendQemu(UpgradeTestBackend):
    " very hacky qemu backend - need qemu >= 0.9.0"

    # FIXME: make this part of the config file
    qemu_binary = "qemu"
    #qemu_binary = "kvm"
    
    qemu_options = [
        "-no-reboot",    # exit on reboot
        "-m","256",        # memory to use
        "-localtime",
        ]

    def __init__(self, profile, basedir):
        UpgradeTestBackend.__init__(self, profile, basedir)

    def _runAptInTarget(self, target, command, cmd_options=[]):
        res = subprocess.call(["chroot", target,
                              "/usr/bin/apt-get",
                              command]+ self.apt_options + cmd_options)
        return res

    def _getProxyLine(self):
        if self.config.has_option("NonInteractive","Proxy"):
            return "export http_proxy=%s" % self.config.get("NonInteractive","Proxy")
        return ""

    def bootstrap(self):
        mirror = self.config.get("NonInteractive","Mirror")
        basepkg = self.config.get("NonInteractive","BasePkg")

        image="/tmp/qemu-upgrade-test.image"
        size=3000
        target="/mnt/qemu-upgrade-test"
        arch = "i386"
        
        if not os.path.exists(target):
            os.mkdir(target)
        # make sure we have nothing mounted left
        subprocess.call(["umount",target])
        # create image
        # FIXME: - make a proper parition table to get grub installed
        #        - create swap (different hdd) as well
        res = subprocess.call(["qemu-img", "create", image, "%sM" % size])
        assert(res == 0)
        res = subprocess.call(["mkfs.ext2","-F",image])
        assert(res == 0)
        res = subprocess.call(["mount","-o","loop,rw",image, target])
        assert(res == 0)
        # FIXME: what we *really* want here is a d-i install with
        #        proper pre-seeding, but debootstrap will have to do for now
        res = subprocess.call(["debootstrap", "--arch", arch, self.fromDist, target, mirror])
        assert(res == 0)
        
        # copy the stuff from toChroot/
        os.chdir("toChroot/")
        for (dirpath, dirnames, filenames) in os.walk("."):
            for name in filenames:
                if not os.path.exists(os.path.join(target,dirpath,name)):
                    print "Copying '%s' to chroot" % os.path.join(target,dirpath,name)
                    shutil.copy(os.path.join(dirpath,name), os.path.join(target,dirpath,name))
        os.chdir("..")

        # setup fstab
        open(target+"/etc/fstab","w").write("""
proc /proc proc defaults 0 0
/dev/hda / ext3 defaults,errors=remount-ro 0 0
""")
        # modify /etc/network/interfaces
        open(target+"/etc/hosts","w").write("""
127.0.0.1 localhost.localdomain localhost
""")
        open(target+"/etc/network/interfaces","w").write("""
auto lo eth0
iface lo inet loopback
iface eth0 inet dhcp
""")
        # FIXME: - what we really want here is to download a kernel-image
        #          to some dir, boot from the dir and run the install
        #          of a new image inside the bootstraped dir (+run grub)
        #        - install grub/lilo/... as well
        res = self._runAptInTarget(target, "clean")
        assert(res == 0)
        res = self._runAptInTarget(target, "install", ["linux-image-generic"])
        assert(res == 0)
        
        # write the first-boot script
        os.mkdir(target+"/upgrade-tester")
        first_boot=target+"/upgrade-tester/first-boot"
        # FIXME: - install NonInteractive/BasePkg
        #        - make sure the thing re-tries, with proxies
        #          a read quite often fails (that we run the install twice)
        open(first_boot,"w").write("""
#!/bin/sh
LOG=/var/log/dist-upgrade/first-boot.log

# proxy (if required)
%s

mkdir /var/log/dist-upgrade
apt-get update > $LOG
apt-get install -y python-apt >> $LOG
apt-get install -y %s >> $LOG
apt-get install -y %s >> $LOG

reboot
""" % (self._getProxyLine(), basepkg, basepkg))
        os.chmod(first_boot, 0755)

        # run the first-boot script
        open(target+"/etc/rc.local","w").write("""
/upgrade-tester/first-boot
""")

        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)
        subprocess.call(["umount", target])
        subprocess.call(["e2fsck", "-p", "-f", "-v", image])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)
        ret = subprocess.call([self.qemu_binary,
                               "-hda", image,
                               "-kernel", "%s/boot/vmlinuz" % target,
                               "-initrd", "%s/boot/initrd.img" % target,
                               "-append", "root=/dev/hda",
                               ]+self.qemu_options)

        # FIXME: find a way to figure if the bootstrap was a success
        subprocess.call(["umount", target])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)
        
        return True

    def upgrade(self):
        # copy the upgrade into target+/upgrader-tester/
        # modify /etc/rc.local to run 
        #  (cd /dist-upgrader ; ./dist-upgrade.py)
        image="/tmp/qemu-upgrade-test.image"
        target="/mnt/qemu-upgrade-test"

        # FIXME: make this more clever
        subprocess.call(["umount",target])
        res = subprocess.call(["mount","-o","loop",image, target])
        assert(res == 0)

        upgrade_tester_dir = os.path.join(target,"upgrade-tester")
        for f in glob.glob("%s/*" % self.basefilesdir):
            if not os.path.isdir(f):
                shutil.copy(f, upgrade_tester_dir)
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to '%s' " % (self.profile, upgrade_tester_dir)
            shutil.copy(self.profile, upgrade_tester_dir)
        # make sure we run the upgrade
        open(target+"/etc/rc.local","w").write("""
#!/bin/sh

LOG=/var/log/dist-upgrade/out.log

#proxy (if required)
%s

mkdir /var/log/dist-upgrade
(cd /upgrade-tester ; ./dist-upgrade.py >> $LOG)

touch /upgrade-tester/upgrade-finished
reboot
""" % self._getProxyLine())

        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)
        subprocess.call(["umount", target])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)

        # start qemu
        # FIXME: - we shouldn't need to pass -kernel, -initrd if
        #          grub is properly runing
        #        - copy the clean image into the profile dir
        ret = subprocess.call([self.qemu_binary,
                               "-hda", image,
                               "-kernel", "%s/boot/vmlinuz" % target,
                               "-initrd", "%s/boot/initrd.img" % target,
                               "-append", "root=/dev/hda",
                              ]+self.qemu_options)
        # FIXME: find a way to figure if the upgrade was a success
        subprocess.call(["umount", target])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)

        # copy the result
        for f in glob.glob(target+"/var/log/dist-upgrade/*"):
            print "copying result to: ", self.resultdir
            shutil.copy(f, self.resultdir)

        return True
                          
        

if __name__ == "__main__":

    # FIXME: very rough proof of conecpt, unify with the chroot
    #        and automatic-upgrade code
    # see also /usr/sbin/qemu-make-debian-root
    
    qemu = UpgradeTestBackendQemu()
    qemu.bootstrap()
    qemu.upgrade()

    # FIXME: now write something into rc.local again and run reboot
    #        and see if we come up with the new kernel
