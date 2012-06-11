#!/usr/bin/python

from __future__ import print_function

import apt_pkg
import glob
import os

(sysname, nodename, krelease, version, machine) = os.uname()

sum = 0
for entry in glob.glob("/boot/*%s*" % krelease):
    sum += os.path.getsize(entry)

print("Sum of kernel related files: ", sum, apt_pkg.size_to_str(sum))
