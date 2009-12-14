# (c) 2005-2009 Canonical, GPL
#

import gobject

class InstallBackend(gobject.GObject):
    """The abstract backend that can install/remove packages"""

    __gsignals__ = {"action-done": (gobject.SIGNAL_RUN_FIRST,
                                    gobject.TYPE_NONE, (gobject.TYPE_INT,))}

    def __init__(self, window_main):
        """init backend
        takes a gtk main window as parameter
        """
        gobject.GObject.__init__(self)
        self.window_main = window_main

    def commit(self, cache):
        """Commit the cache changes """
        raise NotImplemented

    def update(self):
        """Run a update to refresh the package list"""
        raise NotImplemented


