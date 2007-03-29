
import os
import os.path
import logging
import subprocess
import sys


def apport_crash(type, value, tb):
    try:
        from apport.python_hook import apport_excepthook
        from apport.report import Report
    except ImportError, e:
        logging.error("failed to import apport python module, can't report bug: %s" % e)
        return False
    # we pretend we are update-manager
    sys.argv[0] = "/usr/bin/update-manager"
    apport_excepthook(type, value, tb)
    # now add the files in /var/log/dist-upgrade/*
    if os.path.exists('/var/crash/_usr_bin_update-manager.0.crash'):
        report = Report()
        for f in os.listdir("/var/log/dist-upgrade/"):
            report[f.replace(".","")] = (open(os.path.join("/var/log/dist-upgrade",f)), )
        report.add_to_existing('/var/crash/_usr_bin_update-manager.0.crash')
    return True

def apport_pkgfailure(pkg, errormsg):
    LOGDIR="/var/log/dist-upgrader/"
    s = "/usr/share/apport/package_hook"
    if os.path.exists(s):
        p = subprocess.Popen([s,"-p",pkg,"-l",LOGDIR], stdin=subprocess.PIPE)
        p.stdin.write("ErrorMessage: %s\n" % errormsg)
        p.stdin.close()
        return True
    return False

def run_apport():
    for p in ["/usr/share/apport/apport-gtk", "/usr/share/apport/apport-qt"]:
        if os.path.exists(p):
            ret = subprocess.call(p)
            return (ret == 0)
    logging.debug("can't find apport gui")
    return False


if __name__ == "__main__":
    apport_crash(None, None, None)
