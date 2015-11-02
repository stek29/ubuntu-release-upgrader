#!/usr/bin/python3

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

# the first 23 lines are permanent
permanent_lines = 22
lp_mirrors = set()
new_mirrors = set()

for entry in d.entries:
    for link in entry.links:
        lp_mirrors.add(link.href)
        if link.href not in current_mirrors:
            new_mirrors.add(link.href)

with open(sys.argv[1], "w", encoding='utf-8') as outfile:
    for mirror in current_mirrors[:permanent_lines]:
        print(mirror, file=outfile)
    for mirror in current_mirrors[permanent_lines:]:
        if mirror.startswith("#"):
            print(mirror, file=outfile)
        # if it is not in lp_mirrors its not a valid mirror
        if mirror in lp_mirrors:
            print(mirror, file=outfile)
    for mirror in new_mirrors:
        print(mirror, file=outfile)
