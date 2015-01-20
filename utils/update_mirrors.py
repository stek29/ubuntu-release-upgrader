#!/usr/bin/python

import feedparser
import sys

# read what we have
current_mirrors = set()
with open(sys.argv[1], "r") as f:
    for line in f:
        current_mirrors.add(line.strip())

    
d = feedparser.parse("https://launchpad.net/ubuntu/+archivemirrors-rss")

#import pprint
#pp  = pprint.PrettyPrinter(indent=4)
#pp.pprint(d)

with open(sys.argv[1], "a") as outfile:
    for entry in d.entries:
        for link in entry.links:
            if link.href not in current_mirrors:
                outfile.write(link.href + "\n")
