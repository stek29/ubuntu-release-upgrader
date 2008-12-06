#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
from UpdateManager.Common.UpdateList import UpdateList
from UpdateManager.Common.MyCache import MyCache


class testOriginMatcher(unittest.TestCase):
    def setUp(self):
        self.dpkg_status = open("apt/var/lib/dpkg/status","w")
        self.dpkg_status.flush()
        self.cache = MyCache(apt.progress.OpProgress(), rootdir=os.path.join(os.getcwd(),"apt/"))
        self.cache.update()
        self.cache.open(apt.progress.OpProgress())

    def testOriginMatcherSimple(self):
        test_pkgs = set()
        for pkg in self.cache:
            if pkg.candidateOrigin:
                if [l.archive for l in pkg.candidateOrigin
                    if l.archive == "dapper-security"]:
                    test_pkgs.add(pkg.name)
        self.assert_(len(test_pkgs) > 0)
        ul = UpdateList()
        matcher = ul.initMatcher("dapper")
        for pkgname in test_pkgs:
            pkg = self.cache[pkgname]
            self.assertEqual(self.cache.matchPackageOrigin(pkg, matcher),
                             matcher[("dapper-security","Ubuntu")],
                             "pkg '%s' is not in dapper-security but in '%s' instead" % (pkg.name, self.cache.matchPackageOrigin(pkg, matcher).description))
        

    def testOriginMatcherWithVersionInUpdatesAndSecurity(self):
        # empty dpkg status
        self.cache.open(apt.progress.OpProgress())
        
        # find test packages set
        test_pkgs = set()
        for pkg in self.cache:
            if pkg.candidateOrigin:
                for v in pkg.candidateOrigin:
                    if (v.archive == "dapper-updates" and
                        len(pkg._pkg.VersionList) > 2):
                        test_pkgs.add(pkg.name)
        self.assert_(len(test_pkgs) > 0,
                     "no suitable test package found that has a version in both -security and -updates and where -updates is newer")

        # now test if versions in -security are detected
        ul = UpdateList()
        matcher = ul.initMatcher("dapper")
        for pkgname in test_pkgs:
            pkg = self.cache[pkgname]
            self.assertEqual(self.cache.matchPackageOrigin(pkg, matcher),
                             matcher[("dapper-security","Ubuntu")],
                             "package '%s' from dapper-updates contains also a (not yet installed) security updates, but it is not labeled as such" % pkg.name)

        # now check if it marks the version with -update if the -security
        # version is installed
        for pkgname in test_pkgs:
            pkg = self.cache[pkgname]
            # FIXME: make this more inteligent (picking the versin from
            #        -security
            sec_ver = pkg._pkg.VersionList[1]
            self.dpkg_status.write("Package: %s\n"
                              "Status: install ok installed\n"
                              "Installed-Size: 1\n"
                              "Version: %s\n"
                              "Description: foo\n\n"
                              % (pkg.name, sec_ver.VerStr))
            self.dpkg_status.flush()
        self.cache.open(apt.progress.OpProgress())
        for pkgname in test_pkgs:
            pkg = self.cache[pkgname]
            self.assert_(pkg._pkg.CurrentVer != None,
                         "no package '%s' installed" % pkg.name)
            self.assertEqual(self.cache.matchPackageOrigin(pkg, matcher),
                             matcher[("dapper-updates","Ubuntu")],
                             "package '%s' (%s) from dapper-updates is labeld '%s' even though we have marked this version as installed already" % (pkg.name, pkg.candidateVersion, self.cache.matchPackageOrigin(pkg, matcher).description))


if __name__ == "__main__":
    unittest.main()
