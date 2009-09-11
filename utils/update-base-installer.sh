#!/bin/sh

DIST="$(lsb_release -c -s)"
BASEDIR=./apt

APT_OPTS="\
   -o Dir::State=./apt                \
   -o Dir::Cache=./apt                \
   -o Dir::Etc=./apt                  \
   -o Dir::State::Status=./apt/status \
"

# cleanup first
rm -rf base-installer*

# create dirs
if [ ! -d $BASEDIR/archives/partial ]; then
    mkdir -p $BASEDIR/archives/partial
fi

# put right sources.list in
echo "deb-src http://archive.ubuntu.com/ubuntu $DIST main" > $BASEDIR/sources.list

# run apt-get update
apt-get $APT_OPTS update 

# get the latest base-installer
apt-get $APT_OPTS source base-installer
# 
mv base-installer-* base-installer
# FIXME: extract base-installer version info ?
rm -rf base-installer/debian/
mv base-installer ../DistUpgrade