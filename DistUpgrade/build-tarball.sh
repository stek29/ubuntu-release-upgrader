#!/bin/sh

DIST=dapper

# cleanup
rm -f *~ *.bak *.pyc

# make symlink
if [ ! -h $DIST ]; then
       ln -s dist-upgrade.py $DIST
fi

# create the tarbal
tar -c -z -h -v --exclude=debian --exclude=$DIST.tar.gz --exclude=$0 -f $DIST.tar.gz .

scp dapper.tar.gz people:~/public_html/.autoupgrade
