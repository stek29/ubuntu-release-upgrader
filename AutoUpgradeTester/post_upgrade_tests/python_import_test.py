#!/usr/bin/python -u

import logging
import os
import subprocess
import sys


OLD_PYTHONVER="python2.6"
NEW_PYTHONVER="python2.7"

OLD_BASEPATH="/usr/lib/%s/dist-packages/" % OLD_PYTHONVER
NEW_BASEPATH="/usr/lib/%s/dist-packages/" % NEW_PYTHONVER

# stuff that we know does not work when doing a simple "import"
blacklist = ["speechd_config", 
             "PAMmodule.so", 
             "aomodule.so",
             "plannerui.so",
             # needs a KeyringDaemon
             "desktopcouch",
             # just hangs
             "ropemacs",
             ]

def get_module_from_path(path):
    if path and os.path.exists(os.path.join(path, "__init__.py")):
        return f
    elif f.endswith(".py"):
        return f.split(".")[0]
    elif f.endswith(".so"):
        return f.split(".")[0]

def try_import(path):
    logging.info("Importing %s" % path)
    # a simple __import__(module) does not work, the problem
    # is that module import have funny side-effects (like
    # "import uno; import pyatspi" will fail, but importing
    # them individually is fine
    module = get_module_from_path(path)
    if not module:
        logging.debug("could not get module for '%s'" % path)
        return False
    cmd = ["python", "-c","import %s" % module]
    logging.debug("cmd: '%s'" % cmd)
    ret = subprocess.call(cmd)
    if ret != 0:
        print "WARNING: failed to import '%s'" % module
        subprocess.call(["dpkg", "-S", os.path.realpath(path)])
        print "\n\n"
        return False
    return True

def py_module_filter(pymodule):
    f = pymodule
    # ignore a bunch of modules that 
    if (f.endswith(".egg-info") or
        f.endswith(".pth") or 
        f.startswith("_") or
        f.endswith(".pyc") or 
        f.endswith("_d.so") or
        f in blacklist):
        return False
    return True
            
if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)

    old_modules = set(filter(py_module_filter, os.listdir(OLD_BASEPATH)))
    new_modules = set(filter(py_module_filter, os.listdir(NEW_BASEPATH)))
    print "Available for the old version, but *not* the new: %s\n" % (
        ", ".join(old_modules - new_modules))

    res = True
    for f in filter(py_module_filter, os.listdir(NEW_BASEPATH)):
        logging.debug("looking at '%s'" % f)
        res &= try_import(os.path.join(NEW_BASEPATH, f))
        
    if not res:
        sys.exit(1)
