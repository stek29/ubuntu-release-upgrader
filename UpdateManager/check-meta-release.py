from Core.MetaRelease import MetaReleaseCore
import time

metaRelease = MetaReleaseCore(False, False)
while metaRelease.downloading:
    time.sleep(1)
print "no_longer_supported:" + str(metaRelease.no_longer_supported)
if metaRelease.new_dist is None:
    print "new_dist_available:None"
else:
    print "new_dist_available:" + str(metaRelease.new_dist.version)
