#!/usr/bin/python

import feedparser
import sys

# read what we have
current_mirrors = []
with open(sys.argv[1], "r") as f:
    for line in f:
        current_mirrors.append(line.strip())

d = feedparser.parse("https://launchpad.net/ubuntu/+archivemirrors-rss")

#import pprint
#pp  = pprint.PrettyPrinter(indent=4)
#pp.pprint(d)

lp_mirrors = set()
new_mirrors = set()

for entry in d.entries:
    for link in entry.links:
        lp_mirrors.add(link.href)
        if link.href not in current_mirrors:
            new_mirrors.add(link.href)

with open(sys.argv[1], "w") as outfile:
    # the first 23 lines are permanent
    for mirror in current_mirrors[:22]:
        outfile.write(mirror + "\n")
    for mirror in current_mirrors[22:]:
        if mirror.startswith("#"):
            outfile.write(mirror + "\n")
        # its not a valid mirror anymore
        if mirror not in lp_mirrors:
            continue
        outfile.write(mirror + "\n")
    for mirror in new_mirrors:
        outfile.write(mirror + "\n")
