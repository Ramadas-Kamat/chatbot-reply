#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Python Chatbot Reply Generator Unit tests

"""

import unittest

import pycharge

class RuleTestCase(unittest.TestCase):
    pass

class TargetTestCase(unittest.TestCase):
    pass

class ChatbotEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.ch = pycharge.ChatbotEngine()

    def tearDown(self):
        pass

    def test_Load_Error_OnInvalidFilename():
        pass

    def test_Load_Error_OnNoFiles():
        pass

    def test_Load_Error_OnBrokenScript():
        pass

    def test_Load_Error_On_DuplicatePattern():
        pass

    def test_Reply_Error_OnInfiniteRecursion():
        pass

if __name__ == "__main__":
    unittest.main()

    
