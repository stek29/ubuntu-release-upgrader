#!/usr/bin/python
"""
Parse debconf log file and split in a file per prompt
Exit with status 1 if there is a debconf prompt not in whitelist
"""
import re, os, sys

# Keep this path in sync with the corresponding setting in
# profile/defaults.cfg.d/defaults.cfg
DEBCONF_LOG_PATH = '/var/log/dist-upgrade/debconf.log'
RESULT_DIR = '/tmp'

# Prompts in this list won't generate a test failure
# i.e WHITELIST = ['libraries/restart-without-asking']
WHITELIST = [
    'glibc/restart-services',
    'libraries/restart-without-asking' ]

def run_test(logfile, resultdir):
    """ Run the test and slice debconf log

    :param logfile: Path to debconf log
    :param resultdir: Output directory to write log file to
    """
    global WHITELIST

    ret = 0
    if not os.path.exists(logfile):
        return ret

    re_dsetting = re.compile('^\w')
    inprompt = False
    prompt = dsetting = ""

    with open(logfile, 'r') as f_in:
        for line in f_in.readlines():
            # Only keep interesting bits of the prompt
            if line.startswith('#####'):
                inprompt = not inprompt

                # Reached the second separator, write content to result file
                # One per  prompt
                if not inprompt:
                    print "Got debconf prompt for '%s'" % dsetting
                    if dsetting in WHITELIST:
                        print '    But it is in Whitelist. Skipping!'
                        continue
                    else:
                        ret = 1

                    with open(os.path.join(
                        resultdir,
                        'debconf_%s.log' % dsetting.replace('/', '_')),
                        'w') as f_out:
                        f_out.write(prompt)

            if inprompt:
                prompt += line
                if re_dsetting.match(line) and '=' in line:
                    dsetting = line.split('=')[0]

    return ret

if __name__ == '__main__':
    sys.exit(run_test(DEBCONF_LOG_PATH, RESULT_DIR))
