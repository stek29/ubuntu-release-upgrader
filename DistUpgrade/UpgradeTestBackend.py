# TargetNonInteractive.py
#
# abstraction for non-interactive backends (like chroot, qemu)
#


class UpgradeTestBackend(object):
    """ This is a abstrace interface that all backends (chroot, qemu)
        should implement - very basic currently :)
    """
    
    def __init__(self, profile):
        " init the backend with the given profile "
        pass
    
    def bootstrap(self):
        " bootstaps a pristine install"
        pass

    def upgrade(self):
        " upgrade a given install "
        pass

