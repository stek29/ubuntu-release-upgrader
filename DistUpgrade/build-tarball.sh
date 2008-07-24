#!/bin/sh

set -e

DIST=$(lsb_release -c -s)

# cleanup
echo "Cleaning up"
rm -f *~ *.bak *.pyc *.moved '#'* *.rej *.orig
#sudo rm -rf backports/ profile/ result/ tarball/ *.deb

# automatically generate codename for the distro in the 
# cdromupgrade script
sed -i s/^CODENAME=.*/CODENAME=$DIST/ cdromupgrade

# update po
(cd ../po; make update-po)

# update demotions
#(cd ../utils/ ; ./demotions.py )

# make the kde-gui
for file in *.ui; do 
    kdepyuic $file 
done

# copy the mo files
cp -r ../po/mo .

# make symlink
if [ ! -h $DIST ]; then
	ln -s dist-upgrade.py $DIST
fi

# copy the nvidia-modaliases files
mkdir modaliases
cp /usr/share/jockey/modaliases/nvidia-* modaliases

# create the tarball, copy links in place 
tar -c -h -z -v --exclude=$DIST.tar.gz --exclude=$0 -X build-exclude.txt -f $DIST.tar.gz  .


