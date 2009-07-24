import os.path

def backend_factory(*args, **kwargs):
    " get a matching backend "
    if os.path.exists("/usr/sbin/aptd"):
        import InstallBackendAptdaemon
        return InstallBackendAptdaemon.InstallBackendAptdaemon(*args, **kwargs)
    elif os.path.exists("/usr/sbin/synaptic"):
        import InstallBackendSynaptic
        return InstallBackendSynaptic.InstallBackendSynaptic(*args, **kwargs)
    else:
        raise Exception("No working backend found, please try installing synaptic or aptdaemon")

    
