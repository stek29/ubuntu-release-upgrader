# qemu backend

from UpgradeTestBackendSSH import UpgradeTestBackendSSH
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
import atexit
import apt_pkg

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

class UpgradeTestBackendQemu(UpgradeTestBackendSSH):
    " qemu/kvm backend - need qemu >= 0.9.0"

    qemu_options = [
        "-monitor","stdio",
        "-localtime",
        "-no-reboot",    # exit on reboot
        "-no-acpi",      # the dapper kernel does not like qemus acpi
#        "-no-kvm",      # crashes sometimes with kvm HW
        ]

    def __init__(self, profile):
        UpgradeTestBackendSSH.__init__(self, profile)
        self.qemu_pid = None
        self.profiledir = os.path.dirname(profile)
        # get the kvm binary
        self.qemu_binary = self.config.getWithDefault("KVM","KVM","kvm")
        # setup mount dir/imagefile location
        self.baseimage = self.config.get("KVM","BaseImage")
        if not os.path.exists(self.baseimage):
            ret = subprocess.call(["ubuntu-vm-builder","kvm", self.fromDist,
                                   "--kernel-flavour", "generic",
                                   "--ssh-key", "%s.pub" % self.ssh_key ,
                                   "--components", "main,restricted",
                                   "--rootsize", "80000",
                                   "--arch", "i386"])
            # move the disk in place
            shutil.move("ubuntu-kvm/disk0.qcow2",self.baseimage)
            if ret != 0:
                raise NoImageFoundException
        # check if we want virtio here and default to yes
        try:
            virtio = self.config.getboolean("KVM","Virtio")
        except ConfigParser.NoOptionError,e:
            virtio = True
        if virtio:
            self.qemu_options.extend(["-net","nic,model=virtio"])
            self.qemu_options.extend(["-net","user"])
        # swapimage
        if self.config.getWithDefault("KVM","SwapImage",""):
            self.qemu_options.append("-hdb")
            self.qemu_options.append(self.config.get("KVM","SwapImage"))
        # regular image
        profilename = self.config.get("NonInteractive","ProfileName")
        imagedir = self.config.get("KVM","ImageDir")
        self.image = os.path.join(imagedir, "test-image.%s" % profilename)
        # make ssh login possible (localhost 54321) available
        self.ssh_port = self.config.getWithDefault("KVM","SshPort","54321")
        self.ssh_hostname = "localhost"
        self.qemu_options.append("-redir")
        self.qemu_options.append("tcp:%s::22" % self.ssh_port)
        # vnc port/display
        vncport = self.config.getWithDefault("KVM","VncNum","0")
        self.qemu_options.append("-vnc")
        self.qemu_options.append("localhost:%s" % vncport)

        # make the memory configurable
        mem = self.config.getWithDefault("KVM","VirtualRam","768")
        self.qemu_options.append("-m")
        self.qemu_options.append(str(mem))

        # check if the ssh port is in use
        if subprocess.call("netstat -t -l -n |grep 0.0.0.0:%s" % self.ssh_port,
                           shell=True) == 0:
            raise PortInUseException, "the port is already in use (another upgrade tester is running?)"

        # register exit handler to ensure that we quit kvm on exit
        atexit.register(self.stop)

    def genDiff(self):
        """ 
        generate a diff that compares a fresh install to a upgrade.
        ideally that should be empty
        Ensure that we always run this *after* the regular upgrade was
        run (otherwise it is useless)
        """
        # generate ls -R output of test-image (
        self.start()
        ret = self._runInImage(["find", "/bin", "/boot", "/etc/", "/home",
                                "/initrd", "/lib", "/root", "/sbin/",
                                "/srv", "/usr", "/var"],
                               stdout=open(self.resultdir+"/upgrade_install.files","w"))
        ret = self._runInImage(["dpkg","--get-selections"],
                               stdout=open(self.resultdir+"/upgrade_install.pkgs","w"))
        self._runInImage(["tar","cvf","/tmp/etc-upgrade.tar","/etc"])
        self._copyFromImage("/tmp/etc-upgrade.tar", self.resultdir)
        self.stop()

        # HACK: now build fresh toDist image - it would be best if
        self.fromDist = self.config.get("Sources","To")
        self.config.set("Sources","From",
                        self.config.get("Sources","To"))
        diff_image = os.path.join(self.profiledir, "test-image.diff")
        # FIXME: we need to regenerate the base image too, but there is no
        #        way to do this currently without running as root
        # as a workaround we regenerate manually every now and then
        # and use UpgradeFromDistOnBootstrap=true here
        self.config.set("KVM","CacheBaseImage", "false")
        self.config.set("NonInteractive","UpgradeFromDistOnBootstrap","true")
        self.baseimage = "jeos/%s-i386.qcow2" % self.config.get("Sources","To")
        self.image = diff_image
        print "bootstraping into %s" % diff_image
        self.bootstrap()
        print "bootstrap finshsed"
        self.start()
        print "generating file diff list"
        ret = self._runInImage(["find", "/bin", "/boot", "/etc/", "/home",
                                "/initrd", "/lib", "/root", "/sbin/",
                                "/srv", "/usr", "/var"],
                               stdout=open(self.resultdir+"/fresh_install","w"))
        ret = self._runInImage(["dpkg","--get-selections"],
                               stdout=open(self.resultdir+"/fresh_install.pkgs","w"))
        self._runInImage(["tar","cvf","/tmp/etc-fresh.tar","/etc"])
        self._copyFromImage("/tmp/etc-fresh.tar", self.resultdir)
        self.stop()
        # now compare the diffs
        pass

    def bootstrap(self, force=False):
        print "bootstrap()"

        # move old crash files away so that test() is not
        # confused by them
        for f in glob.glob(self.resultdir+"/*.crash"):
            shutil.move(f, f+".old")

        # copy image into place, use baseimage as template
        # we expect to be able to ssh into the baseimage to
        # set it up
        if (not force and
            os.path.exists("%s.%s" % (self.image,self.fromDist)) and 
            self.config.has_option("KVM","CacheBaseImage") and
            self.config.getboolean("KVM","CacheBaseImage")):
            print "Not bootstraping again, we have a cached BaseImage"
            shutil.copy("%s.%s" % (self.image,self.fromDist), self.image)
            return True

        print "Building new image '%s' based on '%s'" % (self.image, self.baseimage)
        shutil.copy(self.baseimage, self.image)

        # get common vars
        mirror = self.config.get("NonInteractive","Mirror")
        basepkg = self.config.get("NonInteractive","BasePkg")
        additional_base_pkgs = self.config.getlist("Distro","BaseMetaPkgs")

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
        assert ret == 0
        # FIXME: instead of this retrying (for network errors with 
        #        proxies) we should have a self._runAptInImage() 
        for i in range(3):
            ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install", "-y",basepkg]+additional_base_pkgs)
        assert ret == 0

        CMAX = 4000
        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        while(len(pkgs)) > 0:
            print "installing additonal: %s" % pkgs[:CMAX]
            ret= self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","install","--reinstall","-y"]+pkgs[:CMAX])
            print "apt(2) returned: %s" % ret
            if ret != 0:
                #self._cacheDebs(tmpdir)
                self.stop()
                return False
            pkgs = pkgs[CMAX+1:]

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            print "have PostBootstrapScript: %s" % script
            if os.path.exists(script):
                self._runInImage(["mkdir","/upgrade-tester"])
                self._copyToImage(script, "/upgrade-tester")
                self._copyToImage(glob.glob(os.path.dirname(
                            self.profile)+"/*.cfg"), "/upgrade-tester")
                script_name = os.path.basename(script)
                self._runInImage(["chmod","755",
                                  os.path.join("/upgrade-tester",script_name)])
                print "running script: %s" % script_name
                cmd = os.path.join("/upgrade-tester",script_name)
                ret = self._runInImage(["cd /upgrade-tester; %s" % cmd])
                print "PostBootstrapScript returned: %s" % ret
                assert ret == 0, "PostBootstrapScript returned non-zero"
            else:
                print "WARNING: %s not found" % script

        if self.config.getWithDefault("NonInteractive",
                                      "UpgradeFromDistOnBootstrap", False):
            print "running apt-get upgrade in from dist (after bootstrap)"
            for i in range(3):
                ret = self._runInImage(["DEBIAN_FRONTEND=noninteractive","apt-get","-y","dist-upgrade"])
            assert ret == 0, "dist-upgrade returned %s" % ret

        print "Cleaning image"
        ret = self._runInImage(["apt-get","clean"])
        assert ret == 0, "apt-get clean returned %s" % ret

        # done with the bootstrap
        self.stop()

        # copy cache into place (if needed)
        if (self.config.has_option("KVM","CacheBaseImage") and
            self.config.getboolean("KVM","CacheBaseImage")):
            shutil.copy(self.image, "%s.%s" % (self.image,self.fromDist))
        
        return True

    def saveVMSnapshot(self,name):
        # savevm
        print "savevm"
        self.stop()
        shutil.copy(self.image, self.image+"."+name)
        return
        # *sigh* buggy :/
        #self.qemu_pid.stdin.write("stop\n")
        #self.qemu_pid.stdin.write("savevm %s\n" % name)
        #self.qemu_pid.stdin.write("cont\n")
    def delVMSnapshot(self,name):
        print "delvm"
        self.qemu_pid.stdin.write("delvm %s\n" % name)
    def restoreVMSnapshot(self,name):
        print "restorevm"
        self.stop()
        shutil.copy(self.image+"."+name, self.image)
	return
        # loadvm
        # *sigh* buggy :/
        #self.qemu_pid.stdin.write("stop\n")
        #self.qemu_pid.stdin.write("loadvm %s\n" % name)
        #self.qemu_pid.stdin.write("cont\n")

    def start(self):
        print "Starting %s %s" % (self.qemu_binary, self.qemu_options)
        if self.qemu_pid != None:
            print "already runing"
            return True
        self.qemu_pid = subprocess.Popen([self.qemu_binary,
                                          "-hda", self.image,
                                          ]+self.qemu_options,
                                         stdin=subprocess.PIPE)
        
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


    def _runBzrCheckoutUpgrade(self):
        # start the upgrader
        print "running the upgrader now"

        # this is to support direct copying of backport udebs into the 
        # qemu image - useful for testing backports without having to
        # push them into the archive
        upgrader_args = ""
        upgrader_env = ""

        backports = self.config.getlist("NonInteractive", "PreRequistsFiles")
        if backports:
            self._runInImage(["mkdir -p /upgrade-tester/backports"])
            for f in backports:
                print "Copying %s" % os.path.basename(f)
                self._copyToImage(f, "/upgrade-tester/backports/")
                self._runInImage(["(cd /upgrade-tester/backports ; dpkg-deb -x %s . )" % os.path.basename(f)])
            upgrader_args = " --have-prerequists"
            upgrader_env = "LD_LIBRARY_PATH=/upgrade-tester/backports/usr/lib PATH=/upgrade-tester/backports/usr/bin:$PATH PYTHONPATH=/upgrade-tester/backports//usr/lib/python$(python -c 'import sys; print \"%s.%s\" % (sys.version_info[0], sys.version_info[1])')/site-packages/ "

        ret = self._runInImage(["(cd /upgrade-tester/ ; "
                                "%s./dist-upgrade.py %s)" % (upgrader_env,
                                                             upgrader_args)])
        return ret

    def upgrade(self):
        print "upgrade()"

        # clean from any leftover pyc files
        for f in glob.glob("%s/*.pyc" %  self.upgradefilesdir):
            os.unlink(f)

        print "Starting for upgrade"
        self.start()

        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to image overrides" % self.profile
            self._runInImage(["mkdir","-p","/etc/update-manager/release-upgrades.d"])
            self._copyToImage(self.profile, "/etc/update-manager/release-upgrades.d/")

        # copy test repo sources.list (if needed)
        test_repo = self.config.getWithDefault("NonInteractive","AddRepo","")
        if test_repo:
            test_repo = os.path.join(os.path.dirname(self.profile), test_repo)
            self._copyToImage(test_repo, "/etc/apt/sources.list.d")
            sourcelist = self.getSourcesListFile()
            apt_pkg.Config.Set("Dir::Etc", os.path.dirname(sourcelist.name))
            apt_pkg.Config.Set("Dir::Etc::sourcelist", 
                               os.path.basename(sourcelist.name))
            sources = SourcesList(matcherPath=".")
            sources.load(test_repo)
            # add the uri to the list of valid mirros in the image
            for entry in sources.list:
                if (not (entry.invalid or entry.disabled) and
                    entry.type == "deb"):
                    print "adding %s to mirrors" % entry.uri
                    self._runInImage(["echo '%s' >> /upgrade-tester/mirrors.cfg" % entry.uri])

        # check if we have a bzr checkout dir to run against or
        # if we should just run the normal upgrader
        if os.path.exists(self.upgradefilesdir):
            self._copyUpgraderFilesFromBzrCheckout()
            ret = self._runBzrCheckoutUpgrade()
        else:
            ret = self._runInImage(["do-release-upgrade","-d",
                                    "-f","DistUpgradeViewNonInteractive"])
        print "dist-upgrade.py returned: %i" % ret

        # copy the result
        print "coyping the result"
        self._copyFromImage("/var/log/dist-upgrade/*",self.resultdir)

        # stop the machine
        print "Shuting down the VM"
        self.stop()

        return (ret == 0)

    def test(self):
        # FIXME: add some tests here to see if the upgrade worked
        # this should include:
        # - new kernel is runing (run uname -r in target)
        # - did it sucessfully rebootet
        # - is X runing
        # - generate diff of upgrade vs fresh install
        # ...
        #self.genDiff()
        self.start()
        self._copyFromImage("/var/crash/*.crash", self.resultdir)
        crashfiles = glob.glob(self.resultdir+"/*.crash")
        self.stop()
        if len(crashfiles) > 0:
            print "WARNING: crash files detected on the upgrade"
            print crashfiles
            return False
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
