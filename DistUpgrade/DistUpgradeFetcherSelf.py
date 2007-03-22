
from DistUpgradeFetcherCore import DistUpgradeFetcherCore

class DistUpgradeFetcherSelf(DistUpgradeFetcherCore):
    def __init__(self, new_dist, progress, options, view):
        DistUpgradeFetcherCore.__init__(self,new_dist,progress)
        self.view = view
        # user seleced to use the network, otherwise it would not be
        # possible to download self
        self.run_options += ["--with-network"]
        # make sure to run self with proper options
        if options.cdromPath is not None:
            self.run_options += ["--cdrom=%s" % options.cdromPath]
        if options.frontend is not None:
            self.run_options += ["--frontend=%s" % options.frontend]

    def error(self, summary, message):
        return self.view.error(summary, message)
