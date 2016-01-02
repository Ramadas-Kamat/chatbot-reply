#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Chatbot Reply Generator Unit tests

"""
from __future__ import print_function
import os
import tempfile
import unittest

from mock import Mock

from chatbot_reply import ChatbotEngine
from chatbot_reply import NoRulesFoundError, InvalidAlternatesError
from chatbot_reply import PatternError, PatternMethodSpecError
from chatbot_reply import MismatchedEncodingsError
from chatbot_reply.reply import Target

class RuleTestCase(unittest.TestCase):
    def test_Rule_Correctly_ComparesByWeightAndScore(self):
        pass
    def test_Rule_Raises_OnInvalidPattern(self):
        pass
    

class TargetTestCase(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    def test_OutputOfTargetTestCase_Formed_Correctly(self):
        problems = [r"ABC_abc 123 !@#$%^&**()-=+|}{[]\~~`';:/.,<>?", "",
                    "Apples, oranges and bananas!", "This one isn't as hard"]
        for p in problems:
            t = Target(p, say=None)
            self.assertEqual(t.orig_text, p)
            self.assertEqual(len(t.orig_words), len(t.tokenized_words))
            for wl in t.tokenized_words:
                self.assertTrue(isinstance(wl, list))
            
            
class ChatbotEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.debuglogger = Mock()
        self.errorlogger = Mock()
        self.ch = ChatbotEngine(debug=True, debuglogger=self.debuglogger,
                                errorlogger=self.errorlogger)
        self.scripts_dir = tempfile.mkdtemp()

    def tearDown(self):
        for item in os.listdir(self.scripts_dir):
            os.remove(os.path.join(self.scripts_dir, item))
        os.rmdir(self.scripts_dir)

    def test_Load_RaisesOSError_OnInvalidDirectory(self):
        self.assertRaises(OSError,
                          self.ch.load_script_directory,
                          os.path.join(self.scripts_dir, "not_there"))

    def test_Load_RaisesNoRulesFoundError_OnNoFiles(self):
        self.assertRaises(NoRulesFoundError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_RaisesSyntaxError_OnBrokenScript(self):
        self.write_py("if True\n\tprint 'syntax error'\n")
        self.assertRaises(SyntaxError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_RaisesNoRulesFoundError_On_NoRules(self):
        py = """
from chatbot_reply import Script
class TestScript(Script):
    pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError, self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_Warning_On_DuplicateRules(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py, filename="foo.py")
        self.write_py(py, filename="bar.py")
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.errorlogger.call_count, 1)
        
    def test_Load_RaisesPatternError_On_MalformedPattern(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("(_)")
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(PatternError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        
    def test_Load_RaisesPatternMethodSpecError_On_UndecoratedMethod(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(PatternMethodSpecError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Reply_Error_OnRuntimeErrorInRule(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("*")
    def pattern_foo(self):
        x = y
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(NameError, self.ch.reply, "local", unicode("test"))
        
    def test_Reply_Chooses_HigherScoringRule(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("hello *")
    def pattern_test1(self):
        return "fail"
    @pattern("* world")
    def pattern_test2(self):
        return "fail"
    @pattern("* *")
    def pattern_test3(self):
        return "fail"
    @pattern("*")
    def pattern_test4(self):
        return "fail"
    @pattern("*~2")
    def pattern_test5(self):
        return "fail"
    @pattern("_* hello")
    def pattern_test6(self):
        return "fail"    
    @pattern("hello world")
    def pattern_test7(self):
        return "pass" 
    @pattern("*2")
    def pattern_test8(self):
        return "fail"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        # this would have a 1 in 8 chance of working anyway due to the
        # lack of hash order, but I tried commenting out sorted() and it
        # triggered the assert.
        # could programatically write 10000 methods with wildcards...
        self.assertEqual(self.ch.reply("local", unicode("hello world")), "pass")
        self.assertFalse(self.errorlogger.called)

    def test_LoadClearLoad_WorksWithoutComplaint(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.ch.clear_rules()
        self.ch.load_script_directory(self.scripts_dir)        
        self.assertFalse(self.errorlogger.called)

    def test_Load_RaisesPatternError_OnMalformedAlternates(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def __init__(self):
        self.alternates = "(hello|world)"
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(InvalidAlternatesError,
                          self.ch.load_script_directory,
                          self.scripts_dir)


    def test_Load_RaisesNoRulesFoundError_OnTopicNone(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def __init__(self):
        self.topic = None
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        pass

    def test_Reply_Passes_MatchedText(self):
        # wait to implement Match object, this is going to change
        pass

        
    def test_Reply_Error_OnInfiniteRecursion(self):
        # not yet implemented
        pass

    def test_Load_RaisesOnMismatchedCodecs(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py, filename="foo.py")
        py = "# coding=latin-1\n" + py
        self.write_py(py, filename="bar.py")
        self.assertRaises(MismatchedEncodingsError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        
    def write_py(self, py, filename="test.py"):
        filename = os.path.join(self.scripts_dir, filename)
        with open(filename, "wb") as f:
            f.write(py + "\n")

if __name__ == "__main__":
    unittest.main()

    
