#!/bin/sh

set -e

# update demotions
(cd utils && ./demotions.py jaunty karmic > demoted.cfg)
# when this gets enabled, make sure to add symlink in DistUpgrade
#(cd utils && ./demotions.py hardy karmic > demoted.cfg.hardy)

# update base-installer
(cd utils && ./update-base-installer.sh)

# cleanup
rm -rf utils/apt/lists utils/apt/*.bin
(cd utils && ./update_mirrors.py ../DistUpgrade/mirrors.cfg)

# run the test-suit
#echo "Running integrated tests"
#(cd tests && for test in *.py; do python $$test; done)

# update version
DEBVER=$(LC_ALL=C dpkg-parsechangelog |sed -n -e '/^Version:/s/^Version: //p' | sed s/.*://)
echo "VERSION='$DEBVER'" > DistUpgrade/DistUpgradeVersion.py

