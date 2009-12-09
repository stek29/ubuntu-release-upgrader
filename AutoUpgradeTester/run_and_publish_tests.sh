#!/bin/sh


RESULTDIR=/var/cache/auto-upgrade-tester/result/

#PROFILES="server ubuntu lts-server lts-ubuntu kubuntu"
PROFILES="lts-server server"
#PROFILES="server"

#UPGRADE_TESTER_ARGS="--tests-only"
UPGRADE_TESTER_ARGS="--quiet"

cat > index.html <<EOF
<?xml version="1.0" encoding="ascii"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
          "DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
  <title>Auto upgrade tester</title>
<style type="text/css">
.error { background-color:#FFFF00 }
table { width:90%; }
</style>
</head>
<body>
<h1>Automatic upgrade tester test results</h1>

<table border="1">
<tr><th>Profile</th><th>Result</th><th>Date</th><th>Runtime</th><th>Full Logs</th></tr>
EOF

FAIL=""
for p in $PROFILES; do
    echo "Testing $p"
    echo -n "<tr><td>$p</td>" >> index.html
    if /usr/bin/time -f %E --output=time.$p ./auto-upgrade-tester $UPGRADE_TESTER_ARGS ./profile/$p; then
        echo -n "<td>OK</td>" >> index.html
    else
     	FAIL="$FAIL $p"
        echo "<td class=\"error\">FAILED</td>" >> index.html
    fi
    echo "<td>$(date +"%F %T")</td><td>$(cat time.$p)</td><td><a href=\"./$p\">Logs for $p test</a></tr>" >> index.html
    cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
-mkdir $p
cd $p
put /var/cache/auto-upgrade-tester/result/$p/*
EOF
    sudo -u $SUDO_USER sftp -b sftp-upload mvo@people.ubuntu.com
done

echo "</table>" >> index.html
echo "</body>" >> index.html

# upload index
cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
put index.html
EOF
sudo -u $SUDO_USER sftp -b sftp-upload mvo@people.ubuntu.com

echo "Tested: $PROFILES"
echo "Failed: $FAIL"
