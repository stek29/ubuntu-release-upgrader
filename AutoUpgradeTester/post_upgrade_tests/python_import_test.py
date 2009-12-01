#!/usr/bin/python

import logging
import os

PYTHONVER="python2.6"
BASEPATH="/usr/lib/%s/dist-packages/" % PYTHONVER

# stuff that we know does not work
blacklist = ["speechd_config", "PAMmodule.so"]

def try_import(module):
    logging.info("Importing %s" % module)
    try:
        m = __import__(module)
        del m
    except:
        logging.exception("import %s failed" % module)
        return False
    return True
            
if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)

    res = True
    for f in os.listdir(BASEPATH):
        if f.endswith(".egg-info") or f.startswith("_") or f in blacklist:
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
