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
from chatbot_reply import PatternError, RuleMethodSpecError
from chatbot_reply import RecursionTooDeepError
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

        self.py_imports = """
from __future__ import unicode_literals
from chatbot_reply import Script, rule
"""

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
        py = self.py_imports + """
class TestScript(Script):
    pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError, self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_Warning_On_DuplicateRules(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py, filename="foo.py")
        self.write_py(py, filename="bar.py")
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.errorlogger.call_count, 1)
        
    def test_Load_RaisesPatternError_On_MalformedPattern(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("(_)")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(PatternError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        
    def test_Load_RaisesRuleMethodSpecError_On_UndecoratedMethod(self):
        py = self.py_imports +  """
class TestScript(Script):
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(RuleMethodSpecError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_LoadClearLoad_WorksWithoutComplaint(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.ch.clear_rules()
        self.ch.load_script_directory(self.scripts_dir)        
        self.assertFalse(self.errorlogger.called)

    def test_Load_Raises_OnMalformedAlternates(self):
        py = self.py_imports + """
class TestScript(Script):
    def setup(self):
        self.alternates = "(hello|world)"
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(InvalidAlternatesError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_RaisesPatternError_OnBadPatternInAlternates(self):
        py = self.py_imports + """
class TestScript(Script):
    def setup(self):
        self.alternates = {"foo": "(hello|world]"}
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(PatternError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        

    def test_Load_RaisesNoRulesFoundError_OnTopicNone(self):
        py = self.py_imports + """
class TestScript(Script):
    def setup(self):
        self.topic = None
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_Raises_WhenRulePassedStr(self):
        py = """
from chatbot_reply import Script, rule
class TestScript(Script):
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(TypeError,
                          self.ch.load_script_directory,
                          self.scripts_dir)
        

    def test_Reply_Passes_MatchedText(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("the number is _# and the word is _@")
    def rule_and_word(self):
        return "results: {match0} {match1}"
    @rule("*", previous="results _*1 _*1")
    def rule_after_results(self):
        return "again: {botmatch0} {botmatch1}"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local",
                                       u"The number is 5 and the word is spam"),
                         u"results: 5 spam")
        self.assertEqual(self.ch.reply("local", u"test"),
                         u"again: 5 spam")
        self.assertFalse(self.errorlogger.called)

    def test_Reply_Matches_RuleWithPrevious(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("_*")
    def rule_star(self):
        return "echo {match0}"
    @rule("*", previous="echo [*]")
    def rule_after_results(self):
        return "echo"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"who"), u"echo who")
        for i in range(100):
            self.assertEqual(self.ch.reply("local", u"who"), u"echo")
        self.assertFalse(self.errorlogger.called)

    def test_Reply_Raises_WithBadRuleReturnString(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("do you like _*")
    def rule_foo(self):
        return "Yes, I love {1}."
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(IndexError,
                          self.ch.reply,"local", u"do you like spam")
        

    def test_Reply_Matches_RuleWithAlternate(self):
        py = self.py_imports + """
class TestScript(Script):
    def __init__(self):
        self.alternates = {"numbers" : "(1|3|5|7|9)"}
    @rule("the number is %a:numbers")
    def rule_number(self):
        return "pass"
    @rule("*")
    def rule_star(self):
        return "fail"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"The number is 5"), "pass")
        self.assertFalse(self.errorlogger.called)
        
    def test_Reply_Matches_RuleWithVariableExpansion(self):
        py = self.py_imports + """
class TestScript(Script):
    def setup(self):
        self.botvars["numbers"] = "(1|3|5|7|9)"
    @rule("the number is %b:numbers")
    def rule_number(self):
        return "pass1"
    @rule("the letter is %u:letters")
    def rule_letter(self):
        return "pass2"
    @rule("set letters")
    def rule_set_letters(self):
        self.uservars["letters"] = "(x|y|z)"
        return "ok"
    @rule("*")
    def rule_star(self):
        return "star"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"The number is 9"), "pass1")
        self.assertEqual(self.ch.reply("local", u"The letter is"), "star")
        self.assertEqual(self.ch.reply("local", u"Set letters."), "ok")
        self.assertEqual(self.ch.reply("local", u"The letter is x"), "pass2")
        self.assertFalse(self.errorlogger.called)        
        
    def test_Reply_RecursivelyExpandsRuleReplies(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("count")
    def rule_foo(self):
        return "one <count2> <count3>"
    @rule("count2")
    def rule_two(self):
        return "two"
    @rule("count3")
    def rule_three(self):
        return "three"    
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", u"count"), u"one two three")
        self.assertFalse(self.errorlogger.called)
        
    def test_Reply_Error_OnRuntimeErrorInRule(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("*")
    def rule_foo(self):
        x = y
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(NameError, self.ch.reply, "local", unicode("test"))
        
    def test_Reply_Chooses_HigherScoringRule(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("hello *")
    def rule_test1(self):
        return "fail"
    @rule("* world")
    def rule_test2(self):
        return "fail"
    @rule("* *")
    def rule_test3(self):
        return "fail"
    @rule("*")
    def rule_test4(self):
        return "fail"
    @rule("*~2")
    def rule_test5(self):
        return "fail"
    @rule("_* hello")
    def rule_test6(self):
        return "fail"    
    @rule("hello world")
    def rule_test7(self):
        return "pass" 
    @rule("*2")
    def rule_test8(self):
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
        py = self.py_imports + """
class TestScript(Script):
    @rule("one")
    def rule_one(self):
        return "<two>"
    @rule("two")
    def rule_two(self):
        return "<one>"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(RecursionTooDeepError,
                          self.ch.reply, "local", u"one")

    def test_Reply_RespondsCorrectly_ToTwoUsers(self):
        py = self.py_imports + """
class TestScript(Script):
    @rule("my name is _@~3")
    def rule_name(self):
        self.uservars["name"] = self.match["match0"]
        return "Nice to meet you!"
    @rule("what did you just say", previous="_*")
    def rule_what(self):
        return 'I just said "{botmatch0}"'
    @rule("what is my name")
    def rule_what_name(self):
        if "name" in self.uservars:
            return "Your name is {0}.".format(self.uservars["name"])
        else:
            return "You haven't told me."
"""
        conversation = [
            (u"one", u"My name is Test One", u"Nice to meet you!"),
            (u"two", u"What is my name?", u"You haven't told me."),
            (u"one", u"What did you just say?", u'I just said "nice to meet you"'),
            (u"two", u"My name is Test Two", u"Nice to meet you!"),
            (u"one", u"What is my name?", u"Your name is test one.")]
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        for user, msg, rep in conversation:
            self.assertEqual(self.ch.reply(user, msg), rep)
        self.assertFalse(self.errorlogger.called)
        
        

    def write_py(self, py, filename="test.py"):
        filename = os.path.join(self.scripts_dir, filename)
        with open(filename, "wb") as f:
            f.write(py + "\n")

if __name__ == "__main__":
    unittest.main()

    
