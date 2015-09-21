#!/bin/sh

set -e

DIST=$(lsb_release -c -s)

# cleanup
echo "Cleaning up"

for d in ./; do
    rm -f $d/*~ $d/*.bak $d/*.pyc $d/*.moved $d/'#'* $d/*.rej $d/*.orig
    rm -rf $d/__pycache__
    rm -f *.tar.gz *.tar
done

#sudo rm -rf backports/ profile/ result/ tarball/ *.deb

# automatically generate codename for the distro in the 
# cdromupgrade script
sed -i s/^CODENAME=.*/CODENAME=$DIST/ cdromupgrade

# update po and copy the mo files
(cd ../po; make update-po)
cp -r ../po/mo .

# make symlink
if [ ! -h $DIST ]; then
	ln -s dist-upgrade.py $DIST
fi

# copy nvidia obsoleted drivers data
cp /usr/share/ubuntu-drivers-common/obsolete ubuntu-drivers-obsolete.pkgs

# create the tarball, copy links in place
tar -c -h -v --exclude DistUpgrade --exclude=$DIST.tar --exclude=$0 -X build-exclude.txt -f $DIST.tar  ./*

# add *.cfg and *.ui to the tarball, copy links (demotions) in place
tar --append -h -v -f $DIST.tar --transform 's|.*/|./|' ../data/*.cfg* ../data/gtkbuilder/*.ui

# add "DistUpgrade"  symlink as symlink
tar --append -v -f $DIST.tar ./DistUpgrade

# and compress it
gzip -9 $DIST.tar
