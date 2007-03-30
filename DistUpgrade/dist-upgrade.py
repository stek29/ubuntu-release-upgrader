#!/usr/bin/python

from DistUpgradeControler import DistUpgradeControler
from DistUpgradeConfigParser import DistUpgradeConfig
import logging
import os
import sys
from optparse import OptionParser
from gettext import gettext as _

if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-c", "--cdrom", dest="cdromPath", default=None,
                      help=_("Use the given path to search for a cdrom with upgradable packages"))
    parser.add_option("--have-backports", dest="haveBackports",
                      action="store_true", default=False)
    parser.add_option("--with-network", dest="withNetwork",action="store_true")
    parser.add_option("--without-network", dest="withNetwork",action="store_false")
    parser.add_option("--frontend", dest="frontend",default=None,
                      help=_("Use frontend. Currently available: \n"\
                             "DistUpgradeViewText, DistUpgradeViewGtk, DistUpgradeViewKDE"))
    parser.add_option("--mode", dest="mode",default="desktop",
                      help=_("Use special upgrade mode. Available:\n"\
                             "desktop, server"))
    (options, args) = parser.parse_args()

    if not os.path.exists("/var/log/dist-upgrade"):
        os.mkdir("/var/log/dist-upgrade")
    logging.basicConfig(level=logging.DEBUG,
                        filename="/var/log/dist-upgrade/main.log",
                        format='%(asctime)s %(levelname)s %(message)s',
                        filemode='w')

    config = DistUpgradeConfig(".")
    # the commandline overwrites the configfile
    for requested_view in [options.frontend]+config.getlist("View","View"):
        if not requested_view:
            continue
        try:
            view_modul = __import__(requested_view)
            view_class = getattr(view_modul, requested_view)
            break
        except (ImportError, AttributeError, TypeError), e:
            logging.warning("can't import view '%s' (%s)" % (requested_view,e))
            print "can't load %s (%s)" % (requested_view, e)
    else:
        logging.error("No view can be imported, aboring")
        print "No view can be imported, aboring"
        sys.exit(1)
    view = view_class()
    app = DistUpgradeControler(view, options)
    app.run()

    # testcode to see if the bullets look nice in the dialog
    #for i in range(4):
    #    view.setStep(i+1)
    #    app.openCache()
