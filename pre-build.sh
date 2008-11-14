#!/bin/sh

# update demotions
#(cd utils && ./demotions.py intrepid jaunty > demotions.cfg)
#(cd utils && ./update_mirrors.py ../DistUpgrade/mirrors.cfg)

# run the test-suit
#echo "Running integrated tests"
#(cd tests && for test in *.py; do python $$test; done)

# update version
echo "VERSION='$(DEBVER)'" > DistUpgrade/DistUpgradeVersion.py

