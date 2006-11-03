
import sys
import os
import apt


from DistUpgradeConfigParser import DistUpgradeConfig
import tempfile
import subprocess
import shutil
import logging
import glob

class Chroot(object):

    diverts = ["/usr/sbin/mkinitrd","/usr/sbin/invoke-rc.d"]
    apt_options = ["-y"]
            
    def __init__(self, profilename, datadir=None, resultdir=None):
        # init the dirs
        self.datadir = datadir
        self.resultdir = resultdir
        self.profilename = profilename
        if not self.datadir:
            self.datadir = os.getcwd()
        if not self.resultdir:
            self.resultdir = os.path.join(os.getcwd(), "result")
        # init the rest
        cname = "DistUpgrade-%s.cfg" % profilename
        profile="%s/profile/DistUpgrade-%s.cfg" % (self.datadir,
                                                   self.profilename)
        if os.path.exists(profile):
            self.profile = profile
            self.config = DistUpgradeConfig(datadir="./profile", name=cname)
                                            
        else:
            raise IOError, "Can't find profile '%s'" % profile
        self.fromDist = self.config.get("Sources","From")
        proxy=self.config.get("NonInteractive","Proxy")
        if proxy:
            os.putenv("http_proxy",proxy)
        os.putenv("DEBIAN_FRONTEND","noninteractive")

    def _runApt(self, tmpdir, command, cmd_options=[]):
        ret = subprocess.call(["chroot",tmpdir, "apt-get", command]
                              +self.apt_options
                              +cmd_options)
        return ret

    def _tryRandomPkgInstall(self, amount):
        " install 'amount' packages randomly "
        self._runApt(tmpdir,"install",["python2.4-apt", "python-apt"])
        shutil.copy("%s/randomInst.py",tmpdir+"/tmp")
        ret = subprocess.call(["chroot",tmpdir,"/tmp/randomInst.py","%s" % amount])

    def bootstrap(self,outfile=None):
        " bootstaps a pristine fromDist tarball"
        if not outfile:
            outfile = os.getcwd() + "/dist-upgrade-%s.tar.gz" % self.fromDist

        tmpdir = tempfile.mkdtemp()
        print "tmpdir is %s" % tmpdir

        print "bootstraping to %s" % outfile
        ret = subprocess.call(["debootstrap", self.fromDist,tmpdir, self.config.get("NonInteractive","Mirror")])
        print "debootstrap returned: %s" % ret

        print "diverting"
        self._dpkgDivert(tmpdir)
        
        print "Updating the chroot"
        ret = self._runApt(tmpdir,"update")
        print "apt returned %s" % ret

        print "installing basepkg"
        ret = self._runApt(tmpdir,"install", [self.config.get("NonInteractive","BasePkg")])
        print "apt returned %s" % ret

        pkgs =  self.config.getListFromFile("NonInteractive","AdditionalPkgs")
        if len(pkgs) > 0:
            print "installing additonal: %s" % pkgs
            ret= self._runApt(tmpdir,"install",pkgs)
            print "apt(2) returned: %s" % ret

        amount = self.config.get("NonInteractive","RandomPkgInstall")
        self._tryRandomPkgInstall(amount)

        print "Cleaning chroot"
        ret = self._runApt(tmpdir,"clean")

        print "building tarball: '%s'" % outfile
        os.chdir(tmpdir)
        ret = subprocess.call(["tar","czf",outfile,"."])
        print "tar returned %s" % ret

        print "Removing chroot"
        shutil.rmtree(tmpdir)

    def upgrade(self, tarball):
        print "runing upgrade on: %s" % tarball
        tmpdir = self._unpackToTmpdir(tarball)
        if not tmpdir:
            print "Error extracting tarball"
        #self._runApt(tmpdir, "install",["apache2"])

        # copy itself to the chroot (resolve symlinks)
        targettmpdir = os.path.join(tmpdir,"tmp","dist-upgrade")
        if not os.path.exists(targettmpdir):
            os.mkdir(targettmpdir)
        for f in glob.glob("%s/*" % self.datadir):
            if not os.path.isdir(f):
                shutil.copy(f, targettmpdir)
        # copy the profile
        if os.path.exists(self.profile):
            print "Copying '%s' to '%s' " % (self.profile,targettmpdir)
            shutil.copy(self.profile,targettmpdir)
            
        # run it
        pid = os.fork()
        if pid == 0:
            os.chroot(tmpdir)
            os.chdir("/tmp/dist-upgrade")
            os.system("mount -t devpts devpts /dev/pts")
            os.system("mount /proc")
            os.execl("/tmp/dist-upgrade/dist-upgrade.py",
                     "/tmp/dist-upgrade/dist-upgrade.py")
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            print "Child exited (%s, %s)" % (id, exitstatus)
            for f in glob.glob(tmpdir+"/var/log/dist-upgrade/*"):
                outdir = os.path.join(self.resultdir,self.profilename)
                if not os.path.exists(outdir):
                    os.makedirs(outdir)
                shutil.copy(f, outdir)
            print "Removing: '%s'" % tmpdir
            os.system("umount %s/dev/pts" % tmpdir)
            os.system("umount %s/proc" % tmpdir)
	    # HACK: try to lazy umount it at least
            os.system("umount -l %s/proc" % tmpdir)
            shutil.rmtree(tmpdir)
            

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
