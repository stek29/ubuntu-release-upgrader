
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
            
    def __init__(self, datadir=None, resultdir=None):
        # init the dirs
        self.datadir = datadir
        self.resultdir = resultdir
        if not self.datadir:
            self.datadir = os.getcwd()
        if not self.resultdir:
            self.resultdir = os.path.join(os.getcwd(), "result")
        # init the rest
        self.config = DistUpgradeConfig()
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
        # run it
        pid = os.fork()
        if pid == 0:
            os.chroot(tmpdir)
            os.execl("/tmp/dist-upgrade/dist-upgrade.py",
                     "/tmp/dist-upgrade/dist-upgrade.py")
        else:
            print "Parent: waiting for %s" % pid
            (id, exitstatus) = os.waitpid(pid, 0)
            print "Child exited (%s, %s)" % (id, exitstatus)
            for f in glob.glob(tmpdir+"/var/log/dist-upgrade/*"):
                shutil.copy(f, self.resultdir)
            print "Removing: '%s'" % tmpdir
            #shutil.rmtree(tmpdir)
            

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
    chroot = Chroot()
    tarball = os.getcwd()+"/tarball/dist-upgrade-test.tar.gz"
    if not os.path.exists(tarball):
        print "No existing tarball found, creating a new one"
        chroot.bootstrap(tarball)
    chroot.upgrade(tarball)

    #tmpdir = chroot._unpackToTmpdir(tarball)
    #chroot._dpkgDivert(tmpdir)
    #print tmpdir
