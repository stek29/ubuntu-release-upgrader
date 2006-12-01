
import sys
import os
import apt


from DistUpgradeConfigParser import DistUpgradeConfig
import tempfile
import subprocess
import shutil
import logging
import glob
import ConfigParser

class Chroot(object):

    diverts = ["/usr/sbin/mkinitrd","/usr/sbin/invoke-rc.d",
	       "/sbin/start-stop-daemon"]
    apt_options = ["-y"]
            
    def __init__(self, profile, basefiledir):
        # init the dirs
        assert(profile != None)
        # the files with the dist-upgrade code
        # (/usr/lib/python2.4/site-packages/DistUpgrade in the deb
        self.resultdir = os.path.abspath(os.path.join(os.path.dirname(profile),"result"))
        self.basefilesdir = os.path.abspath(basefiledir)
        # init the rest
        if os.path.exists(profile):
            self.profile = os.path.abspath(profile)
            self.config = DistUpgradeConfig(datadir=os.path.dirname(profile),
                                            name=os.path.basename(profile))
        else:
            raise IOError, "Can't find profile '%s'" % profile
        
        self.fromDist = self.config.get("Sources","From")
        if self.config.has_option("NonInteractive","Proxy"):
            proxy=self.config.get("NonInteractive","Proxy")
            os.putenv("http_proxy",proxy)
        os.putenv("DEBIAN_FRONTEND","noninteractive")
        self.tarball = None

    def _runInChroot(self, chrootdir, command, cmd_options=[]):
        print "runing: ",command
        pid = os.fork()
        if pid == 0:
            os.chroot(chrootdir)
            os.system("mount -t devpts devpts /dev/pts")
            os.system("mount -t sysfs sysfs /sys")
            os.system("mount /proc")
            os.system("mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc")
            os.execv(command[0], command)
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            os.system("umount %s/dev/pts" % chrootdir)
            os.system("umount %s/proc/sys/fs/binfmt_misc" % chrootdir)
            os.system("umount %s/proc" % chrootdir)
            os.system("umount %s/sys" % chrootdir)
	    # HACK: try to lazy umount it at least
            os.system("umount -l %s/proc" % chrootdir)
            return exitstatus

    def _runApt(self, tmpdir, command, cmd_options=[]):
        ret = self._runInChroot(tmpdir,
                                ["/usr/bin/apt-get", command]+self.apt_options+cmd_options)
        return ret

    def _tryRandomPkgInstall(self, amount):
        " install 'amount' packages randomly "
        self._runApt(tmpdir,"install",["python2.4-apt", "python-apt"])
        shutil.copy("%s/randomInst.py",tmpdir+"/tmp")
        ret = subprocess.call(["chroot",tmpdir,"/tmp/randomInst.py","%s" % amount])

    def bootstrap(self,outfile=None):
        " bootstaps a pristine fromDist tarball"
        if not outfile:
            outfile = os.path.dirname(self.profile) + "/dist-upgrade-%s.tar.gz" % self.fromDist
        outfile = os.path.abspath(outfile)
        self.tarball = outfile

        # don't bootstrap twice if this is something we can cache
        try:
            if (self.config.getboolean("NonInteractive","CacheTarball") and
                os.path.exists(self.tarball) ):
                return True
        except ConfigParser.NoOptionError:
            pass
        
        # bootstrap!
        tmpdir = tempfile.mkdtemp()
        print "tmpdir is %s" % tmpdir

        print "bootstraping to %s" % outfile
        ret = subprocess.call(["debootstrap", self.fromDist,tmpdir, self.config.get("NonInteractive","Mirror")])
        print "debootstrap returned: %s" % ret

        print "diverting"
        self._dpkgDivert(tmpdir)

        # create some minimal device node
        print "Creating some devices"
        os.system("(cd %s/dev ; echo $PWD; ./MAKEDEV null)" % tmpdir)
        #self._runInChroot(tmpdir, ["/bin/mknod","/dev/null","c","1","3"])

        # write new sources.list
        if (self.config.has_option("NonInteractive","Components") and
            self.config.has_option("NonInteractive","Pockets")):
            comps = self.config.getlist("NonInteractive","Components")
            pockets = self.config.getlist("NonInteractive","Pockets")
            mirror = self.config.get("NonInteractive","Mirror")
            sourceslist = open(tmpdir+"/etc/apt/sources.list","w")
            sourceslist.write("deb %s %s %s\n" % (mirror, self.fromDist, " ".join(comps)))
            for pocket in pockets:
                sourceslist.write("deb %s %s-%s %s\n" % (mirror, self.fromDist,pocket, " ".join(comps)))
            sourceslist.close()
            
            print open(tmpdir+"/etc/apt/sources.list","r").read()
        
        print "Updating the chroot"
        ret = self._runApt(tmpdir,"update")
        print "apt update returned %s" % ret
        if ret != 0:
            return False
        ret = self._runApt(tmpdir,"dist-upgrade")
        print "apt dist-upgrade returned %s" % ret
        if ret != 0:
            return False

        print "installing basepkg"
        ret = self._runApt(tmpdir,"install", [self.config.get("NonInteractive","BasePkg")])
        print "apt returned %s" % ret
        if ret != 0:
            return False

        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        if len(pkgs) > 0:
            print "installing additonal: %s" % pkgs
            ret= self._runApt(tmpdir,"install",pkgs)
            print "apt(2) returned: %s" % ret
            if ret != 0:
                return False

        if self.config.has_option("NonInteractive","PostBootstrapScript"):
            script = self.config.get("NonInteractive","PostBootstrapScript")
            if os.path.exists(script):
                shutil.copy(script, os.path.join(tmpdir,"tmp"))
                self._runInChroot(tmpdir,[os.path.join("/tmp",script)])
            else:
                print "WARNING: %s not found" % script

        try:
            amount = self.config.get("NonInteractive","RandomPkgInstall")
            self._tryRandomPkgInstall(amount)
        except ConfigParser.NoOptionError:
            pass

        print "Cleaning chroot"
        ret = self._runApt(tmpdir,"clean")
        if ret != 0:
            return False

        print "building tarball: '%s'" % outfile
        os.chdir(tmpdir)
        ret = subprocess.call(["tar","czf",outfile,"."])
        print "tar returned %s" % ret

        print "Removing chroot"
        shutil.rmtree(tmpdir)
        return True

    def upgrade(self, tarball=None):
        if not tarball:
            tarball = self.tarball
        assert(tarball != None)
        print "runing upgrade on: %s" % tarball
        tmpdir = self._unpackToTmpdir(tarball)
        if not tmpdir:
            print "Error extracting tarball"
        #self._runApt(tmpdir, "install",["apache2"])

        # copy itself to the chroot (resolve symlinks)
        targettmpdir = os.path.join(tmpdir,"tmp","dist-upgrade")
        if not os.path.exists(targettmpdir):
            os.mkdir(targettmpdir)
        for f in glob.glob("%s/*" % self.basefilesdir):
            if not os.path.isdir(f):
                shutil.copy(f, targettmpdir)
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to '%s' " % (self.profile,targettmpdir)
            shutil.copy(self.profile, targettmpdir)
            
        # run it
        pid = os.fork()
        if pid == 0:
            os.chroot(tmpdir)
            os.chdir("/tmp/dist-upgrade")
            os.system("mount -t devpts devpts /dev/pts")
            os.system("mount -t sysfs sysfs /sys")
            os.system("mount /proc")
            os.system("mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc")
            os.execl("/tmp/dist-upgrade/dist-upgrade.py",
                     "/tmp/dist-upgrade/dist-upgrade.py")
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            print "Child exited (%s, %s)" % (id, exitstatus)
            for f in glob.glob(tmpdir+"/var/log/dist-upgrade/*"):
                print "copying result to: ", self.resultdir
                shutil.copy(f, self.resultdir)
            print "Removing: '%s'" % tmpdir
            os.system("umount %s/dev/pts" % tmpdir)
            os.system("umount %s/proc/sys/fs/binfmt_misc" % tmpdir)
            os.system("umount %s/proc" % tmpdir)
            os.system("umount %s/sys" % tmpdir)
	    # HACK: try to lazy umount it at least
            os.system("umount -l %s/proc" % tmpdir)
            shutil.rmtree(tmpdir)
            return (exitstatus == 0)

    def _unpackToTmpdir(self, baseTarBall):
        tmpdir = tempfile.mkdtemp()
        os.chdir(tmpdir)
        ret = subprocess.call(["tar","xzf",baseTarBall])
        if ret != 0:
            return None
        return tmpdir

    def _dpkgDivert(self, tmpdir):
        for d in self.diverts:
            cmd = ["chroot",tmpdir,
                   "dpkg-divert","--add","--local",
                   "--divert",d+".thereal",
                   "--rename",d]
            ret = subprocess.call(cmd)
            shutil.copy(tmpdir+"/bin/true",tmpdir+d)
    

if __name__ == "__main__":
    if len(sys.argv) > 1:
        profilename = sys.argv[1]
    else:
	profilename = "default"
    chroot = Chroot(profilename)
    tarball = "%s/tarball/dist-upgrade-%s.tar.gz" % (os.getcwd(),profilename)
    if not os.path.exists(tarball):
        print "No existing tarball found, creating a new one"
        chroot.bootstrap(tarball)
    chroot.upgrade(tarball)

    #tmpdir = chroot._unpackToTmpdir(tarball)
    #chroot._dpkgDivert(tmpdir)
    #print tmpdir
