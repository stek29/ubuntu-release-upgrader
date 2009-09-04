#!/bin/sh

set -e

DIST=$(lsb_release -c -s)

# cleanup
echo "Cleaning up"

for d in ./ plugins/ computerjanitor/; do
    rm -f $d/*~ $d/*.bak $d/*.pyc $d/*.moved $d/'#'* $d/*.rej $d/*.orig
done

#sudo rm -rf backports/ profile/ result/ tarball/ *.deb

# automatically generate codename for the distro in the 
# cdromupgrade script
sed -i s/^CODENAME=.*/CODENAME=$DIST/ cdromupgrade

# update po
(cd ../po; make update-po)

# update demotions
#(cd ../utils/ ; ./demotions.py )

# copy the mo files
cp -r ../po/mo .

# make symlink
if [ ! -h $DIST ]; then
	ln -s dist-upgrade.py $DIST
fi

# copy the nvidia-modaliases files
if [ ! -d modaliases ]; then
    mkdir modaliases 
fi
cp /usr/share/jockey/modaliases/nvidia-* modaliases
cp /usr/share/jockey/modaliases/fglrx* modaliases

# get the base-installer from bzr but remove the debian/ dir
bzr co --lightweight lp:~ubuntu-core-dev/base-installer/ubuntu base-installer
rm -rf base-installer/debian

# create the tarball, copy links in place 
tar -c -h -z -v --exclude=$DIST.tar.gz --exclude=$0 -X build-exclude.txt -f $DIST.tar.gz  ./*


