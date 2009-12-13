#!/bin/sh

# -------------------------------------------------------------- config
# link to the ssh key to publish the results
SSHKEY="-oIdentityFile=link-to-ssh-key"
PUBLISH="mvo@people.ubuntu.com"
#PUBLISH=""

RESULTDIR=/var/cache/auto-upgrade-tester/result/

PROFILES="dapper-hardy-lucid-server dapper-hardy-lucid-ubuntu server ubuntu lts-server lts-ubuntu kubuntu"
#PROFILES="lts-server server"
#PROFILES="server"

#UPGRADE_TESTER_ARGS="--tests-only"
UPGRADE_TESTER_ARGS="--quiet"

# ------------------------------------------------------------- main()

cat > index.html <<EOF
<?xml version="1.0" encoding="ascii"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
          "DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
  <title>Auto upgrade tester</title>
<style type="text/css">
.error { background-color:#FFFF00; }
.aright { text-align:right; }
table { width:90%; }
</style>
</head>
<body>
<h1>Automatic upgrade tester test results</h1>

<p>Upgrade test started $(date +"%F %T")</p>

<table border="1">
<tr><th>Profile</th><th>Result</th><th>Date Finished</th><th>Runtime</th><th>Full Logs</th></tr>
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
    echo "<td>$(date +"%F %T")</td><td class=\"aright\">$(cat time.$p)</td><td><a href=\"./$p\">Logs for $p test</a></tr>" >> index.html
    cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
-mkdir $p
cd $p
put /var/cache/auto-upgrade-tester/result/$p/*
EOF
    sftp $SSHKEY -b sftp-upload $PUBLISH >/dev/null
done

echo "<p>Upgrade test finished $(date +"%F %T")</p>" >> index.html

echo "</table>" >> index.html
echo "</body>" >> index.html

# upload index
cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
put index.html
EOF
sftp $SSHKEY -b sftp-upload $PUBLISH >/dev/null

echo "Tested: $PROFILES"
if [ -n "$FAIL" ]; then
    echo "Failed: $FAIL"
fi
