#!/usr/bin/python
# coding=utf-8
#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Unit tests for Python Chatbot Reply Generator's Pattern Parser """
from __future__ import unicode_literals

from chatbot_reply import PatternParser, PatternError

import re
import sys
import traceback
import unittest

class PatternParserTestCase(unittest.TestCase):
    def setUp(self):
        self.pp = PatternParser()

    def tearDown(self):
        pass

    def test_PP_RaisesExceptions_On_InvalidInput(self):
        problems = ["", "$", "!", 
                    "foo *(x)", "foo @_a", "foo #[x!", "(x)#", "*%b", "la*la",
                    "_", "_abc", "*_", " _ ", "_%x:foo", "_|", "_ *"
                    "foo(", "foo@", "foo[", "foo^", "%u:foo(bar)"
                    "          ",
                    "%x:", "%xyzzy", "%", "  %:", "%x:foo", "%x:(ysy)", "%(:",
                    "%a", "%a:_zzz", "%b:123", "%u:*", "%u:[yyy]",
                    "]","foo]", "*]", "(foo])", ")))", "()", "(()))", "[[[]]",
                    "|", "a|b", "a | b", "(a|)", "[|]", "(foo)(bar)" ]

        for p in problems:
            self._assertRaises(PatternError, self.pp.parse, p)

    def test_PP_RaisesExceptions_On_InvalidInput_in_SimpleMode(self):
        problems = ["*", "u%foo", "_(hello|goodbye)"]

        for p in problems:
            self._assertRaises(PatternError,
                               lambda x:self.pp.parse(x, simple=True), p)

    def _assertRaises(self, error, func, arg):
        """ asserts and prints out what the argument was """
        try:
            func(arg)
            print 'Failed on "{0}"'.format(arg)
            self.assertFalse(True)
        except error:
            pass
        except Exception as e:
            print 'Failed on "{0}" with {1}'.format(arg, e)
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60

            self.assertFalse(True)

    def test_PP_FormatOfParse_Equals_Input(self):
        problems = ["* hello world # @ @6~ @3~5 #~4 *7 %u:hello_world %b:x %a:foo",
                    "(hello world|%u:zzz|lalala|_[97]) [*|#~22]",
                    "(hello world|[foobarbaz|(%u:u|%a:a|foo)]|xyzzy)"]
        for p in problems:
            self.assertEqual(p, self.pp.format(self.pp.parse(p)))

    def test_PP_Regex_Succeeds_on_SomeOfEverything(self):
        problems = ["* hello world # @ @1~ #~2 @1~2 *1 *2 %u:hello_world %b:x %a:foo",
                    "(hello world|%u:zzz|lalala|_[97]) [*|#~2]",
                    "(hello world|[foobarbaz|(%u:u|%a:a|foo)]|xyzzy)"]
        for p in problems:
            self.pp.format(self.pp.parse(p))

    def test_PP_Matching(self):
        problems = [("hello",
                     ["hello"],
                     ["goodbye"]),
                    ("i feel (good|fine|ok)",
                     ["i feel good", "i feel fine", "i feel ok"],
                     ["i feel bad", "i feel"]),
                    ("i feel _( good | fine | ok)",
                     ["i feel good", "i feel fine", "i feel ok"],
                     ["i feel bad", "i feel "]),
                    ("how [are] you",
                     ["how are you", "how you"],
                     ["how", "you"]),
                    ("my name is %u:name",
                     ["my name is fred"],
                     ["my name is"]),
                    ("call me [%u:name]",
                     ["call me fred", "call me"],
                     []),
                    ("%b:mood to meet ([mr|mrs] %u:name|you)",
                     ["good to meet you", "good to meet fred",
                      "good to meet mrs fred"],
                     ["good to meet", "good to meet mr"]),
                    ("voilà",
                     ["voilà"],
                     ["voila"]),
                    ("my car is %a:colors",
                     ["my car is red", "my car is blue", "my car is light yellow"],
                     ["my car is ", "my car is"]),
                    ("the answer is %b:under_score",
                     ["the answer is yes"],
                     []),
                    ("my @1 car is my favorite",
                     ["my green car is my favorite"],
                     ["my car is my favorite", "my 2nd car is my favorite"],
                     ["my light green car is my favorite"]),
                    ("my [*1] car is my favorite",
                     ["my car is my favorite",
                      "my green car is my favorite"],
                     ["my light green car is my favorite"]),
                    ("the numbers are #~3",
                     ["the numbers are 1", "the numbers are 1 2",
                      "the numbers are 1 2 3"],
                     ["the numbers are 1 2 3 4", "the numbers are a b c"]),
                    ("*5~ is the word",
                     ["x y z z y is the word", "x y z z y 6 is the word"],
                     ["x y z z is the word"]),
                    ("my (red|blue|[*1] green) car",
                     ["my red car", "my green car", "my light green car"],
                     ["my light red car", "my car", "my foobar car"]),
                    ("* or something",
                     ["lunch or something", "5 dollars or something"],
                     ["or something", "that or something else"]),
                    ("[*] the machine [*]",
                     ["what about the machine", "the machine is broken",
                      "why dont you tell me about the machine", "the machine"],
                     ["the washing machine"]),
                    ]
                     
        variables = {"u": {"name":"Fred", "city":"bedrock"},
                     "a": {"colors":"(red|blue|light yellow)"},
                     "b": {"mood": "good", "under_score" : "yes"}}

        for p in problems:
            pattern = p[0]
            regex = self.pp.regex(self.pp.parse(pattern), variables) + "$"
            regexc = re.compile(regex, re.UNICODE)
            for good in p[1]:
                match = re.match(regexc, good)
                if match is None:
                    print 'Failed to match "{0}" with "{1}" using regex "{2}"'.format(
                        pattern, good, regex)
                    self.assertFalse(True)
            for bad in p[2]:
                match = re.match(regexc, bad)
                if match is not None:
                    print 'Matched incorrectly "{0}" with "{1}" using regex "{2}"'.format(
                        pattern, bad, regex)
                    self.assertFalse(True)

    def test_PP_Scoring(self):
        self.assertTrue(self.score("hello mom") > self.score("hello"))
        self.assertTrue(self.score("hello *") < self.score("hello"))
        self.assertTrue(self.score("hello") == self.score("(hello|goodbye)"))
        self.assertTrue(self.score("hello world") == self.score("hello %u:foo"))
        self.assertTrue(self.score("[a|b c|d]") == self.score("b c"))
        self.assertTrue(self.score("(a|[b] c d|e)") == self.score("b c d"))
        self.assertTrue(self.score("@") > self.score("*"))
        self.assertTrue(self.score("#") > self.score("*"))
        

    def test_PP_Memorization(self):
        problems = [("my _(car|truck) is _*", "my car is fast", ["car", "fast"]),
                    ("my _[red|blue] car", "my red car", ["red"]),
                    ("my _[red|blue] car", "my car", [""]),
                    ("my _@~2 car", "my very fast car", ["very fast"]),
                    ]
        for p in problems:
            regex = self.pp.regex(self.pp.parse(p[0]), None)
            m = re.match(regex, p[1])
            if m is None:
                print "Failed to match {0} with {1}".format(p[0], p[1])
                self.assertTrue(m is not None)
            d = m.groupdict()
            if len(p[2]) != len(d):
                print "Matched {0} with {1} and got {2}".format(
                    p[0], p[1], d)
                self.assertTrue(False)

            for i in range(len(d)):
                if d["match"+str(i)] != p[2][i]:
                    print "Matched {0} with {1} and got {2}".format(
                        p[0], p[1], d)
                    self.assertTrue(False)                    
                   
            
        
    def score(self, string):
        return self.pp.score(self.pp.parse(string))

if __name__ == "__main__":
    unittest.main()

            
