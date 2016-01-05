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
from chatbot_reply import MismatchedEncodingsError, RecursionTooDeepError
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

    def test_Load_Raises_OnMalformedAlternates(self):
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

    def test_Load_RaisesPatternError_OnBadPatternInAlternates(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def __init__(self):
        self.alternates = {"foo": "(hello|world]"}
    @pattern("hello")
    def pattern_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(PatternError,
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
        

    def test_Reply_Passes_MatchedText(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("the number is _# and the word is _@")
    def pattern_and_word(self):
        return "results: {match0} {match1}"
    @pattern("*", previous="results _*1 _*1")
    def pattern_after_results(self):
        return "again: {botmatch0} {botmatch1}"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local",
                                       u"The number is 5 and the word is spam"),
                         u"results: 5 spam")
        self.assertEqual(self.ch.reply("local", u"test"),
                         u"again: 5 spam")


    def test_Reply_Matches_RuleWithAlternate(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def __init__(self):
        self.alternates = {"numbers" : "(1|3|5|7|9)"}
    @pattern("the number is %a:numbers")
    def pattern_number(self):
        return "pass"
    @pattern("*")
    def pattern_star(self):
        return "fail"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"The number is 5"), "pass")
        
    def test_Reply_Matches_RuleWithVariableExpansion(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    def __init__(self):
        Script.botvars["numbers"] = "(1|3|5|7|9)"
    @pattern("the number is %b:numbers")
    def pattern_number(self):
        return "pass1"
    @pattern("the letter is %u:letters")
    def pattern_letter(self):
        return "pass2"
    @pattern("set letters")
    def pattern_set_letters(self):
        Script.uservars["letters"] = "(x|y|z)"
        return "ok"
    @pattern("*")
    def pattern_star(self):
        return "star"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"The number is 9"), "pass1")
        self.assertEqual(self.ch.reply("local", u"The letter is"), "star")
        self.assertEqual(self.ch.reply("local", u"Set letters."), "ok")
        self.assertEqual(self.ch.reply("local", u"The letter is x"), "pass2")
        
        
    def test_Reply_RecursivelyExpandsRuleReplies(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("count")
    def pattern_foo(self):
        return "one <count2> <count3>"
    @pattern("count2")
    def pattern_two(self):
        return "two"
    @pattern("count3")
    def pattern_three(self):
        return "three"    
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"count"), u"one two three")

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
        self.assertEqual(self.ch.reply("local", u"hello world"), "pass")
        self.assertFalse(self.errorlogger.called)

    def test_Reply_Error_OnInfiniteRecursion(self):
        py = """
from chatbot_reply import Script, pattern
class TestScript(Script):
    @pattern("one")
    def pattern_one(self):
        return "<two>"
    @pattern("two")
    def pattern_two(self):
        return "<one>"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(RecursionTooDeepError,
                          self.ch.reply, "local", u"one")

    def write_py(self, py, filename="test.py"):
        filename = os.path.join(self.scripts_dir, filename)
        with open(filename, "wb") as f:
            f.write(py + "\n")

if __name__ == "__main__":
    unittest.main()

    
