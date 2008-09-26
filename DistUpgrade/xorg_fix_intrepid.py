#!/usr/bin/python
#
# this script will exaimne /etc/xorg/xorg.conf and 
# transition from broken proprietary drivers to the free ones
#

import apt
import sys
import os.path

XORG_CONF="/etc/X11/xorg.conf"

def replace_driver_from_xorg(old_driver, new_driver, xorg=XORG_CONF):
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
            s.endswith('"%s"' % old_driver)):
            line='\tDriver\t"%s"\n' % new_driver
        content.append(line)
    # write out the new version
    if open(xorg).readlines() != content:
        print "rewriting %s (%s -> %s)" % (xorg, old_driver, new_driver)
        open(xorg,"w").write("".join(content))

if __name__ == "__main__":
    print "%s running" % sys.argv[0]

    if not os.path.exists(XORG_CONF):
        print "No xorg.conf" 
        sys.exit(0)

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/fglrx_drv.so") and
        "fglrx" in open(XORG_CONF).read()):
        print "Removing fglrx from %s" % XORG_CONF
        replace_driver_from_xorg("fglrx","ati")

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/nvidia_drv.so") and
        "nvidia" in open(XORG_CONF).read()):
        print "Removing nvidia from %s" % XORG_CONF
        replace_driver_from_xorg("nvidia","nv")

