# (c) 2005-2009 Canonical, GPL
#

class InstallBackend(object):
    """The abstract backend that can install/remove packages"""
    def __init__(self, window_main):
        """init backend
        takes a gtk main window as parameter
        """
        self.window_main = window_main

    def commit(self, cache):
        """Commit the cache changes """

    def update(self):
        """Run a update to refresh the package list"""


