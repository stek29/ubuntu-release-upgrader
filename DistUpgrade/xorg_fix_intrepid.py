#!/usr/bin/python
#
# this script will exaimne /etc/xorg/xorg.conf and 
# transition from broken proprietary drivers to the free ones
#

import apt
import sys
import os
import os.path
import logging

XORG_CONF="/etc/X11/xorg.conf"

def replace_driver_from_xorg(old_driver, new_driver, xorg=XORG_CONF):
    """
    this removes the fglrx driver from the xorg.conf and subsitutes
    it with the ati one
    """
    if not os.path.exists(xorg):
        logging.warning("file %s not found" % xorg)
        return
    content=[]
    for line in open(xorg):
        # remove comments
        s=line.split("#")[0].strip()
        # check for fglrx driver entry
        if (s.startswith("Driver") and
            s.endswith('"%s"' % old_driver)):
            logging.debug("line '%s' found" % line)
            line='\tDriver\t"%s"\n' % new_driver
            logging.debug("replacing with '%s'" % line)
        content.append(line)
    # write out the new version
    if open(xorg).readlines() != content:
        logging.info("saveing new %s (%s -> %s)" % (xorg, old_driver, new_driver))
        open(xorg,"w").write("".join(content))

if __name__ == "__main__":
    if not os.getuid() == 0:
        print "Need to run as root"
        sys.exit(1)

    logging.basicConfig(level=logging.DEBUG,
                        filename="/var/log/dist-upgrade/xorg_fix_intrepid.log",
                        filemode='w')
    
    logging.info("%s running" % sys.argv[0])

    if not os.path.exists(XORG_CONF):
        logging.info("No xorg.conf, exiting")
        sys.exit(0)

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/fglrx_drv.so") and
        "fglrx" in open(XORG_CONF).read()):
        logging.info("Removing fglrx from %s" % XORG_CONF)
        replace_driver_from_xorg("fglrx","ati")

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/nvidia_drv.so") and
        "nvidia" in open(XORG_CONF).read()):
        logging.info("Removing nvidia from %s" % XORG_CONF)
        replace_driver_from_xorg("nvidia","nv")

