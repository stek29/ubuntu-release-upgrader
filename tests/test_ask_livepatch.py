#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: nil; tab-width: 4; coding: utf-8 -*-

import os
import unittest
from DistUpgrade.DistUpgradeController import (
    DistUpgradeController,
)

import mock

CURDIR = os.path.dirname(os.path.abspath(__file__))


class testLivepatch(unittest.TestCase):

    testdir = os.path.abspath(CURDIR + "/data-sources-list-test/")

    @mock.patch("os.path.isfile")
    def testFromLTStoNonLTS(self, mock_isfile):
        """
        Livepatch notice appears on upgrade from LTS to non-LTS
        """
        # fake '/var/snap/canonical-livepatch/common/machine-token'
        mock_isfile.return_value = True
        v = mock.Mock()
        v.askCancelContinueQuestion.return_value = False
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = 'bionic'
        d.toDist = 'cosmic'
        d.askLivepatch()
        self.assertTrue(mock_isfile.called)
        self.assertTrue(v.askCancelContinueQuestion.called)

    @mock.patch("os.path.isfile")
    def testFromNonLTS(self, mock_isfile):
        """
        Livepatch notice does not appear on upgrade of non-LTS
        """
        # fake '/var/snap/canonical-livepatch/common/machine-token'
        mock_isfile.return_value = True
        v = mock.Mock()
        v.askCancelContinueQuestion.return_value = False
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = 'cosmic'
        d.toDist = 'disco'
        d.askLivepatch()
        self.assertFalse(mock_isfile.called)
        self.assertFalse(v.askCancelContinueQuestion.called)

    @mock.patch("os.path.isfile")
    def testFromLTStoLTS(self, mock_isfile):
        """
        Livepatch notice does not appear on upgrade from LTS to LTS
        """
        # fake '/var/snap/canonical-livepatch/common/machine-token'
        mock_isfile.return_value = True
        v = mock.Mock()
        v.askCancelContinueQuestion.return_value = False
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = 'xenial'
        d.toDist = 'bionic'
        d.askLivepatch()
        self.assertTrue(mock_isfile.called)
        self.assertFalse(v.askCancelContinueQuestion.called)

    @mock.patch("os.path.isfile")
    def testNoLivePatch(self, mock_isfile):
        mock_isfile.return_value = False
        v = mock.Mock()
        v.askCancelContinueQuestion.return_value = False
        d = DistUpgradeController(v, datadir=self.testdir)
        d.fromDist = 'bionic'
        d.toDist = 'cosmic'
        d.askLivepatch()
        self.assertTrue(mock_isfile.called)
        self.assertFalse(v.askCancelContinueQuestion.called)


if __name__ == "__main__":
    unittest.main()
