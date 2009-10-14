import os
import os.path

def backend_factory(*args, **kwargs):
    " get a matching backend "

    # try synaptic
    if (os.path.exists("/usr/sbin/synaptic") and 
        not "UPDATE_MANAGER_FORCE_BACKEND_APTDAEMON" in os.environ):
        import InstallBackendSynaptic
        return InstallBackendSynaptic.InstallBackendSynaptic(*args, **kwargs)


    # try the aptdaemon
    if os.path.exists("/usr/sbin/aptd"):
        # check if the gtkwidgets are installed as well
        try:
            import aptdaemon.gtkwidgets
            import InstallBackendAptdaemon
            return InstallBackendAptdaemon.InstallBackendAptdaemon(*args, **kwargs)
        except ImportError, e:
            pass

    # nothing found, raise
    raise Exception("No working backend found, please try installing synaptic or aptdaemon")

    
