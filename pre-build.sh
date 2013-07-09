#!/bin/sh

set -e

# The testsuite has a sad if you're in a non-UTF-8 locale:
export LANG='C.UTF-8'

dpkg-checkbuilddeps -d 'python3-apt, apt-btrfs-snapshot, parsewiki, python-feedparser,
			python3-mock, xvfb, gir1.2-gtk-3.0, python3-gi, python3-nose'

# update demotions
(cd utils && ./demotions.py quantal raring > demoted.cfg)
# when this gets enabled, make sure to add symlink in DistUpgrade
#(cd utils && ./demotions.py lucid precise > demoted.cfg.lucid)

# update base-installer
(cd utils && ./update-base-installer.sh)

# update apt_btrfs_snapshot.py copy, this needs an installed
# apt-btrfs-snapshot on the build machine
if [ ! -e /usr/share/pyshared/apt_btrfs_snapshot.py ]; then
    echo "please sudo apt-get install apt-btrfs-snapshot"
    exit 1
fi
cp /usr/share/pyshared/apt_btrfs_snapshot.py DistUpgrade

# (auto) generate the required html
if [ ! -x /usr/bin/parsewiki ]; then
    echo "please sudo apt-get install parsewiki"
    exit 1
fi
(cd DistUpgrade; 
 parsewiki DevelReleaseAnnouncement > DevelReleaseAnnouncement.html;
 parsewiki ReleaseAnnouncement > ReleaseAnnouncement.html;
 parsewiki EOLReleaseAnnouncement > EOLReleaseAnnouncement.html;
)

# cleanup
rm -rf utils/apt/lists utils/apt/*.bin
(cd utils && ./update_mirrors.py ../data/mirrors.cfg)

# run the test-suite
#echo "Running integrated tests"
nosetests3

# test leftovers
rm -f ./tests/data-sources-list-test/apt.log

# update version
DEBVER=$(LC_ALL=C dpkg-parsechangelog |sed -n -e '/^Version:/s/^Version: //p' | sed s/.*://)
echo "VERSION='$DEBVER'" > DistUpgrade/DistUpgradeVersion.py
