
import os
import os.path
import subprocess

def run_apport(pkg, errormsg):
    LOGDIR="/var/log/dist-upgrader/"
    s = "/usr/share/apport/package_hook"
    if os.path.exists(s):
        p = subprocess.Popen([s,"-p",pkg,"-l",LOGDIR], stdin=subprocess.PIPE)
        p.stdin.write("ErrorMessage: %s\n" % errormsg)
        p.stdin.close()
        return True
    return False
