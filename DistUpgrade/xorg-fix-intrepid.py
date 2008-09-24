#!/usr/bin/python
#
# this script will exaimne /etc/xorg/xorg.conf and 
# transition from broken proprietary drivers to the free ones
#

import apt
import sys
import os.path

def remove_fglrx_from_xorg(xorg="/etc/xorg/xorg.conf"):
    """
    this removes the fglrx driver from the xorg.conf and subsitutes
    it with the ati one
    """
    if not os.path.exists(xorg):
        return
    content=[]
    for line in open(xorg):
        # remove comments
        s=line.split("#")[0].strip()
        # check for fglrx driver entry
        if (s.startswith("Driver") and
            s.endswith('"fglrx"')):
            line='\tDriver\t"ati"\n'
        content.append(line)
    # write out the new version
    if open(xorg).readlines() != content:
        open(xorg,"w").write("".join(content))

if __name__ == "__main__":
    print "%s running" % sys.argv[0]

    if not os.path.exists("/usr/lib/xorg/modules/drivers/fglrx_drv.so"):
        remove_fglrx_from_xorg()

