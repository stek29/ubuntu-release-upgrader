# TargetNonInteractive.py
#
# abstraction for non-interactive backends (like chroot, qemu)
#

from DistUpgrade.DistUpgradeConfigParser import DistUpgradeConfig

try:
    import configparser
except ImportError:
    import ConfigParser as configparser
import os
import tempfile
from shutil import rmtree

# refactor the code so that we have
# UpgradeTest - the controler object
# UpgradeTestImage - abstraction for chroot/qemu/xen

class UpgradeTestImage(object):
    def runInTarget(self, command):
        pass
    def copyToImage(self, fromFile, toFile):
        pass
    def copyFromImage(self, fromFile, toFile):
        pass
    def bootstrap(self, force=False):
        pass
    def start(self):
        pass
    def stop(self):
        pass

class UpgradeTestBackend(object):
    """ This is a abstrace interface that all backends (chroot, qemu)
        should implement - very basic currently :)
    """

    apt_options = ["-y","--allow-unauthenticated"]

    def __init__(self, profiledir, resultdir=""):
        " init the backend with the given profile "
        # init the dirs
        assert(profiledir != None)
        profiledir = os.path.normpath(profiledir)
        profile = os.path.join(os.path.abspath(profiledir), "DistUpgrade.cfg")
        self.upgradefilesdir = "./DistUpgrade"

        if os.path.exists("./post_upgrade_tests/"):
            self.post_upgrade_tests_dir = "./post_upgrade_tests/"
        else:
            self.post_upgrade_tests_dir = "/usr/share/auto-upgrade-tester/post_upgrade_tests/"
        # init the rest
        if os.path.exists(profile):
            override_cfg_d = os.path.join(profiledir, "..", "override.cfg.d")
            defaults_cfg_d = os.path.join(profiledir, "..", "defaults.cfg.d")
            self.profile = os.path.abspath(profile)
            self.config = DistUpgradeConfig(datadir=os.path.dirname(profile),
                                            name=os.path.basename(profile),
                                            override_dir=override_cfg_d,
                                            defaults_dir=defaults_cfg_d)
        else:
            raise IOError("Can't find profile '%s' (%s) " % (profile, os.getcwd()))
        if resultdir:
            base_resultdir = resultdir
        else:
            base_resultdir = self.config.getWithDefault(
                "NonInteractive", "ResultDir", "results-upgrade-tester")
        self.resultdir = os.path.abspath(
            os.path.join(base_resultdir, profiledir.split("/")[-1]))

        # Cleanup result directory before new run
        if os.path.exists(self.resultdir):
            rmtree(self.resultdir)
        os.makedirs(self.resultdir)
        
        self.fromDist = self.config.get("Sources","From")
        if "http_proxy" in os.environ and not self.config.has_option("NonInteractive","Proxy"):
            self.config.set("NonInteractive","Proxy", os.environ["http_proxy"])
        elif self.config.has_option("NonInteractive","Proxy"):
            proxy=self.config.get("NonInteractive","Proxy")
            os.putenv("http_proxy",proxy)
        os.putenv("DEBIAN_FRONTEND","noninteractive")
        self.cachedir = None
        try:
            self.cachedir = self.config.get("NonInteractive","CacheDebs")
        except configparser.NoOptionError:
            pass
        # init a sensible environment (to ensure proper operation if
        # run from cron)
        os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"

    def installPackages(self, pkgs):
        """
        install packages in the image
        """
        pass

    def getSourcesListFile(self):
        """
        creates a temporary sources.list file and returns it to 
        the caller
        """
        # write new sources.list
        sourceslist = tempfile.NamedTemporaryFile()
        comps = self.config.getlist("NonInteractive","Components")
        pockets = self.config.getlist("NonInteractive","Pockets")
        mirror = self.config.get("NonInteractive","Mirror")
        sourceslist.write("deb %s %s %s\n" % (mirror, self.fromDist, " ".join(comps)))
        for pocket in pockets:
            sourceslist.write("deb %s %s-%s %s\n" % (mirror, self.fromDist,pocket, " ".join(comps)))
        sourceslist.flush()
        return sourceslist
    
    def bootstrap(self):
        " bootstaps a pristine install"
        pass

    def upgrade(self):
        " upgrade a given install "
        pass

    def test(self):
        " test if the upgrade was successful "
        pass

    def resultsToJunitXML(self, results, outputfile = None):
        """
        Filter results to get Junit XML output

        :param results: list of results. Each result is a dictionary of the form
            name: name of the test
            result: (pass, fail, error)
            time: execution time of the test in seconds
            message: optional message in case of failure or error
        :param output: Output XML to this file instead of returning the value
        """
        from xml.sax.saxutils import escape

        output = ""
        testsuite_name = ''
        res = [x['result'] for x in results]
        fail_count = res.count('fail')
        error_count = res.count('error')
        total_count = len(res)
        total_time = sum([x['time'] for x in results])

        output = """<testsuite errors="%d" failures="%d" name="%s" tests="%d" time="%.3f">\n""" % (
            error_count, fail_count, testsuite_name, total_count,total_time)

        for result in results:
            output += """<testcase classname="%s" name="%s" time="%.3f">\n""" % (
                self.profilename + '.PostUpgradeTest',
                result['name'][:-3], result['time'])
            if 'fail' in result['result']:
                output += """<failure type="%s">%s\n</failure>\n""" % (
                    'exception', escape(result['message']))
            elif 'error' in result['result']:
                output += """<error type="%s">%s\n</error>\n""" % (
                    'exception', escape(result['message']))

            output += "</testcase>\n"
        output += "</testsuite>\n"

        if outputfile:
            with open(outputfile, 'w') as f:
                f.write(output)
        else:
            return output
