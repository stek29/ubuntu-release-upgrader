#!/bin/sh

DIST=edgy

# cleanup
rm -f *~ *.bak *.pyc *.moved '#'*

# make symlink
if [ ! -h $DIST ]; then
       ln -s dist-upgrade.py $DIST
fi

# create the tarball, copy links in place 
tar -c -h -z -v --exclude=debian --exclude=$DIST.tar.gz --exclude=$0 -f $DIST.tar.gz .


scp dapper.tar.gz people:~/public_html/.autoupgrade
