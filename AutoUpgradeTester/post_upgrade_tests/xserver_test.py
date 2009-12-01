#!/usr/bin/python

import os
import subprocess
import sys

if os.path.exists("/usr/bin/X"):
    proclist = subprocess.Popen(["ps","-eo","comm"], stdout=subprocess.PIPE).communicate()[0]
    for line in proclist.split("\n"):
        if line == "Xorg":
            break
    else:
        print "WARNING: /usr/bin/X found but no Xorg running"
        sys.exit(1)
