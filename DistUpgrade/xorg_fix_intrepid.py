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
import time
import shutil

XORG_CONF="/etc/X11/xorg.conf"

def removeInputDevices(xorg_source=XORG_CONF, xorg_destination=XORG_CONF):
    try:
        from XKit import xutils, xorgparser
    except Exception, e:
        logging.error("failed to import xkit (%s)" % e)
        return False

    # parse
    try:
        a = xutils.XUtils(xorg_source)
    except xorgparser.ParseException, e:
        logging.error("failed to parse '%s' (%s)" % (xorg_source, e))
        return False

    # remove any input device
    logging.info("removing InputDevice from %s " % xorg_source)
    a.globaldict['InputDevice'] = {}

    # remove any reference to input devices from the ServerLayout
    a.removeOption('ServerLayout', 'InputDevice', 
                   value=None, position=None, reference=None)
    # write the changes to temp file and move into place
    print xorg_destination+".new"
    a.writeFile(xorg_destination+".new")
    os.rename(xorg_destination+".new", xorg_destination)
    return True

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
        open(xorg+".xorg_fix","w").write("".join(content))
        os.rename(xorg+".xorg_fix", xorg)

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
        
    #make a backup of the xorg.conf
    backup = XORG_CONF + "_dist-upgrade." + time.strftime("%Y%m%d%H%M%S")
    shutil.copy(XORG_CONF, backup)

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/fglrx_drv.so") and
        "fglrx" in open(XORG_CONF).read()):
        logging.info("Removing fglrx from %s" % XORG_CONF)
        replace_driver_from_xorg("fglrx","ati")

    if (not os.path.exists("/usr/lib/xorg/modules/drivers/nvidia_drv.so") and
        "nvidia" in open(XORG_CONF).read()):
        logging.info("Removing nvidia from %s" % XORG_CONF)
        replace_driver_from_xorg("nvidia","nv")

    # now run the removeInputDevices()
    removeInputDevices(xorg_destination="/tmp/foox")
