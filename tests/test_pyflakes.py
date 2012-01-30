#!/usr/bin/python

import subprocess
import unittest

class TestPyflakesClean(unittest.TestCase):
    """ ensure that the tree is pyflakes clean """

    def test_pyflakes_clean(self):
        # mvo: type -f here to avoid running pyflakes on imported files
        #      that are symlinks to other packages
        cmd = 'find .. -type f -name "*.py"|xargs  pyflakes'
        self.assertEqual(subprocess.call(cmd, shell=True), 0)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
