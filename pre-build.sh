#!/bin/sh

set -e

# FIXME: this can go away and become a symlink in DistUpgrade/apt_clone.py
#        once apt-clone is accetped into the distro
if [ ! -e /usr/share/pyshared/apt_clone.py ]; then
    echo "Need a installed apt-clone (lp:apt-clone) to continue"
    exit 1
fi
cp /usr/share/pyshared/apt_clone.py DistUpgrade


# update demotions
(cd utils && ./demotions.py maverick natty > demoted.cfg)
# when this gets enabled, make sure to add symlink in DistUpgrade
#(cd utils && ./demotions.py hardy lucid > demoted.cfg.hardy)

# update base-installer
(cd utils && ./update-base-installer.sh)

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
(cd utils && ./update_mirrors.py ../DistUpgrade/mirrors.cfg)

# run the test-suit
#echo "Running integrated tests"
(cd tests && make)

# test leftovers
rm -f ./tests/data-sources-list-test/apt.log

# update version
DEBVER=$(LC_ALL=C dpkg-parsechangelog |sed -n -e '/^Version:/s/^Version: //p' | sed s/.*://)
echo "VERSION='$DEBVER'" > DistUpgrade/DistUpgradeVersion.py

