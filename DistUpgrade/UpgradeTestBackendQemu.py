# qemu backend

from UpgradeTestBackend import UpgradeTestBackend

import subprocess
import os.path
import shutil
import glob

class QemuUpgradeTestBackend(UpgradeTestBackend):
    " very hacky qemu backend "

    def __init__(self):
        self.apt_options = ["-y","--allow-unauthenticated"]

    def _runAptInTarget(self, target, command, cmd_options=[]):
        res = subprocess.call(["chroot", target,
                              "/usr/bin/apt-get",
                              command]+ self.apt_options + cmd_options)
        return res

    def bootstrap(self):
        image="/tmp/qemu-upgrade-test.image"
        size=1500
        target="/mnt/qemu-upgrade-test"
        fromDist = "edgy"
        mirror = "http://de.archive.ubuntu.com/ubuntu"
        arch = "i386"
        
        if not os.path.exists(target):
            os.mkdir(target)
        # make sure we have nothing mounted left
        subprocess.call(["umount",target])
        # create image
        # FIXME: - make a proper parition table to get grub installed
        #        - create swap (different hdd) as well
        #        - use qemu-img instead of dd
        res = subprocess.call(["dd",
                               "if=/dev/zero",
                               "of=%s" % image,
                               "bs=1M",
                               "count=%s" % size])
        assert(res == 0)
        res = subprocess.call(["mkfs.ext2","-F",image])
        assert(res == 0)
        res = subprocess.call(["mount","-o","loop,rw",image, target])
        assert(res == 0)
        # FIXME: what we *really* want here is a d-i install with
        #        proper pre-seeding, but debootstrap will have to do for now
        res = subprocess.call(["debootstrap", "--arch", arch, fromDist, target, mirror])
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
/dev/hda / ext3 defaults,errors=remount-ro 0 1
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
        # FIXME: install NonInteractive/BasePkg
        open(first_boot,"w").write("""
#!/bin/sh
LOG=/upgrade-tester/first-boot.log

export http_proxy=http://10.0.2.2:3128/

apt-get update > $LOG
apt-get install -y python-apt >> $LOG
apt-get install -y ubuntu-standard >> $LOG

touch /upgrade-tester/first-boot-finished
""")
        os.chmod(first_boot, 0755)

        # run the first-boot script
        open(target+"/etc/rc.local","w").write("""
/upgrade-tester/first-boot
""")

        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)
        subprocess.call(["umount", target])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)
        
        try: os.unlink("qemu.pid")
        except: pass
        res = subprocess.call(["qemu",
                               "-pidfile", "qemu.pid",
                               "-hda", image,
                               "-kernel", "%s/boot/vmlinuz" % target,
                               "-initrd", "%s/boot/initrd.img" % target,
                               "-append", "root=/dev/hda",
                               ])
        # FIXME: - find a way to know when qemu actually finished
        #          (runing halt does not seem to stop it, currently 
        #           the window needs to be closed manually (sucks big time)
        #        - copy the clean image into the profile dir

    def upgrade(self):
        # copy the upgrade into target+/upgrader-tester/
        # modify /etc/rc.local to run 
        #  (cd /dist-upgrader ; ./dist-upgrade.py)
        basefilesdir = "."
        profile = "profile/server/DistUpgrade.cfg"
        image="/tmp/qemu-upgrade-test.image"
        target="/mnt/qemu-upgrade-test"

        # FIXME: make this more clever
        subprocess.call(["umount",target])
        res = subprocess.call(["mount","-o","loop",image, target])
        assert(res == 0)

        upgrade_tester_dir = os.path.join(target,"upgrade-tester")
        for f in glob.glob("%s/*" % basefilesdir):
            if not os.path.isdir(f):
                shutil.copy(f, upgrade_tester_dir)
        # copy the profile
        if os.path.exists(profile):
            print "Copying '%s' to '%s' " % (profile, upgrade_tester_dir)
            shutil.copy(profile, upgrade_tester_dir)
        # make sure we run the upgrade
        open(target+"/etc/rc.local","w").write("""
#!/bin/sh

LOG=/var/log/dist-upgrade/out.log
export http_proxy=http://10.0.2.2:3128/

mkdir /var/log/dist-upgrade
(cd /upgrade-tester ; ./dist-upgrade.py >> $LOG)

touch /upgrade-tester/upgrade-finished
""")

        # remount, ro to read the kernel (sync + mount -o remount,ro might
        # work as well)
        subprocess.call(["umount", target])
        res = subprocess.call(["mount","-o","loop,ro",image, target])
        assert(res == 0)

        # start qemu
        try: os.unlink("qemu.pid")
        except: pass
        # we shouldn't need to pass -kernel, -initrd if grub is properly
        # runing
        res = subprocess.call(["qemu",
                               "-pidfile", "qemu.pid",
                               "-hda", image,
                               "-kernel", "%s/boot/vmlinuz" % target,
                               "-initrd", "%s/boot/initrd.img" % target,
                               "-append", "root=/dev/hda",
                               ])
        # FIXME: same as in bootstrap, we currently do not know
        #        when qemu is finished
        

if __name__ == "__main__":

    # FIXME: very rough proof of conecpt, unify with the chroot
    #        and automatic-upgrade code
    # see also /usr/sbin/qemu-make-debian-root
    
    qemu = QemuUpgradeTestBackend()
    qemu.bootstrap()
    qemu.upgrade()

    # FIXME: now write something into rc.local again and run reboot
    #        and see if we come up with the new kernel
