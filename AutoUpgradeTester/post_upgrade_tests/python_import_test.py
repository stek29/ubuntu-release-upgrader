#!/usr/bin/python

import logging
import os
import subprocess
import sys


PYTHONVER="python2.6"
BASEPATH="/usr/lib/%s/dist-packages/" % PYTHONVER

# stuff that we know does not work when doing a simple "import"
blacklist = ["speechd_config", 
             "PAMmodule.so", 
             "aomodule.so",
             "plannerui.so",
             # needs a KeyringDaemon
             "desktopcouch",
             ]

def try_import(module):
    logging.info("Importing %s" % module)
    # a simple __import__(module) does not work, the problem
    # is that module import have funny side-effects (like
    # "import uno; import pyatspi" will fail, but importing
    # them individually is fine
    cmd = ["python", "-c","import %s" % module]
    logging.debug("cmd: '%s'" % cmd)
    ret = subprocess.call(cmd)
    if ret != 0:
        print "WARNING: failed to import '%s'" % module
        return False
    return True
            
if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)

    res = True
    for f in os.listdir(BASEPATH):
        # ignore a bunch of modules that 
        if (f.endswith(".egg-info") or 
            f.startswith("_") or 
            f.endswith("_d.so") or
            f in blacklist):
            continue
        logging.debug("looking at '%s'" % f)
        if os.path.isdir(BASEPATH+f) and os.path.exists(BASEPATH+f+"/__init__.py"):
            res &= try_import(f)
        elif f.endswith(".py"):
            res &= try_import(f.split(".")[0])
        elif f.endswith(".so"):
            res &= try_import(f.split(".")[0])
    
    if not res:
        sys.exit(1)
