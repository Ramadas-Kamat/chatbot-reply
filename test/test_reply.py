# coding=utf-8
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Chatbot Reply Generator Unit tests

"""
from __future__ import print_function
import logging
import os
import shutil
import tempfile
import unittest

from mock import Mock

from chatbot_reply import ChatbotEngine
from chatbot_reply import PatternError, RecursionTooDeepError, NoRulesFoundError
from chatbot_reply.reply import Target

class TestHandler(logging.Handler):
    def emit(self, record):
        pass
testhandler = TestHandler()
testhandler.setLevel(logging.WARNING)
logging.getLogger().addHandler(testhandler)
    
class TargetTestCase(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    def test_OutputOfTargetTestCase_Formed_Correctly(self):
        problems = [r"ABC_abc 123 !@#$%^&**()-=+|}{[]\~~`';:/.,<>?", "",
                    "Apples, oranges and bananas!", "This one isn't as hard"]
        for p in problems:
            t = Target(p, [])
            self.assertEqual(t.raw_text, p)
            self.assertEqual(len(t.raw_words), len(t.tokenized_words))
            for wl in t.tokenized_words:
                self.assertTrue(isinstance(wl, list))
            
            
class ChatbotEngineTestCase(unittest.TestCase):
    def setUp(self):

        self.errorlogger = testhandler.emit = Mock()
        self.ch = ChatbotEngine()
        self.scripts_dir = tempfile.mkdtemp()

        self.py_imports = b"""
from __future__ import unicode_literals
from chatbot_reply import Script, rule
"""
        self.py_encoding = b"# coding=utf-8\n"

    def tearDown(self):
        shutil.rmtree(self.scripts_dir)

    def test_Load_RaisesOSError_OnInvalidDirectory(self):
        self.assertRaises(OSError,
                          self.ch.load_script_directory,
                          os.path.join(self.scripts_dir, "not_there"))

    def test_Load_RaisesNoRulesFoundError_OnNoFiles(self):
        self.assertRaises(NoRulesFoundError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_RaisesSyntaxError_OnBrokenScript(self):
        self.write_py(b"if True\n\tprint 'syntax error'\n")
        self.assertRaises(SyntaxError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_RaisesNoRulesFoundError_On_NoRules(self):
        py = self.py_imports + b"""
class TestScript(Script):
    pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError, self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_Warning_On_DuplicateRules(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py, filename="foo.py")
        self.write_py(py, filename="bar.py")
        testhandler.setLevel(logging.WARNING)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.errorlogger.call_count, 1)
        
    def test_Load_RaisesPatternError_On_MalformedPattern(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("(_)")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaisesCheckMessage(PatternError, "test.TestScript.rule_foo",
                          self.ch.load_script_directory,
                          self.scripts_dir)
        
    def test_Load_Raises_On_UndecoratedMethod(self):
        py = self.py_imports + b"""
class TestScript(Script):
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaisesCheckMessage(TypeError, "test.TestScript.rule_foo",
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_LoadClearLoad_WorksWithoutComplaint(self):
        # this creates a file not closed warning on python 3, but
        # I think it's python's bug not mine
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py, filename="loadclearload.py")
        self.ch.load_script_directory(self.scripts_dir)
        self.ch.clear_rules()
        self.ch.load_script_directory(self.scripts_dir)        
        self.assertFalse(self.errorlogger.called)

    def test_Load_Raises_OnMalformedAlternates(self):
        py = self.py_imports + b"""
class TestScript(Script):
    def setup(self):
        self.alternates = "(hello|world)"
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaisesCheckMessage(AttributeError,
                                      "alternates of test.TestScript",
                                      self.ch.load_script_directory,
                                      self.scripts_dir)

    def test_Load_RaisesPatternError_OnBadPatternInAlternates(self):
        py = self.py_imports + b"""
class TestScript(Script):
    def setup(self):
        self.alternates = {"foo": "(hello|world]"}
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaisesCheckMessage(PatternError,
                                      'alternates["foo"] of test.TestScript',
                                      self.ch.load_script_directory,
                                      self.scripts_dir)
        

    def test_Load_RaisesNoRulesFoundError_OnTopicNone(self):
        py = self.py_imports + b"""
class TestScript(Script):
    topic = None
    @rule("hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaises(NoRulesFoundError,
                          self.ch.load_script_directory,
                          self.scripts_dir)

    def test_Load_Raises_WhenRulePassedByteStr(self):
        py = b"""
from chatbot_reply import Script, rule
class TestScript(Script):
    @rule(b"hello")
    def rule_foo(self):
        pass
"""
        self.write_py(py)
        self.assertRaisesCheckMessage(TypeError, "test.Testscript.rule_foo",
                          self.ch.load_script_directory,
                          self.scripts_dir)
        

    def test_Reply_Passes_MatchedText(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("the number is _# and the word is _@")
    def rule_and_word(self):
        return "results: {match0} {match1}"
    @rule("*", previous_reply="results _*1 _*1")
    def rule_after_results(self):
        return "again: {reply_match0} {reply_match1}"
    @rule("my name is _@1 _@1")
    def rule_my_name_is(self):
        return "I'll put you down as {raw_match1}, {raw_match0}."
    @rule("play it again sam", previous_reply="_* as _*")
    def rule_play_it_again(self):
        return ("The first part was '{raw_reply_match0}' "
                "and the second part was '{raw_reply_match1}'.")
"""
        conversation = [("local", u"The number is 5 and the word is spam",
                         u"results: 5 spam"),
                        ("local", u"test", u"again: 5 spam"),
                        ("local", u"My name is Fred Flintstone",
                         u"I'll put you down as Flintstone, Fred."),
                        ("local", u"Play it again, Sam!",
                         u"The first part was 'I'll put you down' and the "
                         u"second part was 'Flintstone, Fred.'.")
                        ]

        self.have_conversation(py, conversation)

    def test_Reply_Matches_RuleWithPrevious(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("_*")
    def rule_star(self):
        return "echo {match0}"
    @rule("*", previous_reply="echo [*]")
    def rule_after_results(self):
        return "echo"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertEqual(self.ch.reply("local", {}, u"who"), u"echo who")
        for i in range(100):
            self.assertEqual(self.ch.reply("local", {}, u"who"), u"echo")
        self.assertFalse(self.errorlogger.called)

    def test_Reply_Raises_WithBadRuleReturnString(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("do you like _*")
    def rule_foo(self):
        return "Yes, I love {1}."
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaisesCheckMessage(IndexError, "test.TestScript.rule_foo",
                                      self.ch.reply,"local", {}, u"do you like spam")

    def test_Reply_Raises_WithBadSubstitutionsReturnValue(self):
        py = self.py_imports + b"""
class TestScript(Script):
    def substitute(self, text, things):
        things.append(text)
        return things
    @rule("*")
    def rule_star(self):
        return "anything"
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaisesCheckMessage(TypeError, "test.TestScript.rule_foo",
                                      self.ch.reply,"local", {}, u"do you like spam")
        
        

    def test_Reply_Matches_RuleWithAlternate(self):
        py = self.py_imports + b"""
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
        self.have_conversation(py, [("local", u"The number is 5", "pass")])
        
    def test_Reply_Matches_RuleWithVariableExpansion(self):
        py = self.py_imports + b"""
class TestScript(Script):
    def setup(self):
        self.botvars["numbers"] = "(1|3|5|7|9)"
        self.alternates = {"colors": "(red|green|blue)"}
    def setup_user(self, user):
        self.uservars["letters"] = "(x|y|z)"
    @rule("the number is %b:numbers")
    def rule_number(self):
        return "pass1"
    @rule("the letter is %u:letters")
    def rule_letter(self):
        return "pass2"
    @rule("the mistake is %b:undefined")
    def rule_mistake(self):
        return "fail"
    @rule("i need %b:numbers %a:colors %u:letters")
    def rule_need(self):
        return "pass3"
    @rule("say it")
    def rule_say_it(self):
        return "number 5 color blue letter x"
    @rule("check it", 
          previous_reply="number %b:numbers color %a:colors letter %u:letters")
    def rule_check_it(self):
        return "pass4"
    @rule("*")
    def rule_star(self):
        return "star"
"""
        conversation = [("local", u"The number is 9", u"pass1"),
                        ("local", u"The letter is x", u"pass2"),
                        ("local", u"The mistake is", u"star"),
                        ("local", u"I need 1 green z", u"pass3"),
                        ("local", u"Say it", u"number 5 color blue letter x"),
                        ("local", u"Check it", u"pass4"),
                        ("local", u"Check it", u"star")]
        
        self.have_conversation(py, conversation)
        
    def test_Reply_RecursivelyExpandsRuleReplies(self):
        py = self.py_imports + b"""
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
        self.have_conversation(py, [("local", u"count", u"one two three")])
        
    def test_Reply_Raises_OnRuntimeErrorInRule(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("*")
    def rule_foo(self):
        x = y
"""
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        self.assertRaises(NameError, self.ch.reply, "local", {}, u"test")
        
    def test_Reply_Chooses_HigherScoringRule(self):
        py = self.py_imports + b"""
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
        self.assertEqual(self.ch.reply("local", {}, u"hello world"), "pass")
        self.assertFalse(self.errorlogger.called)

    def test_Reply_Error_OnInfiniteRecursion(self):
        py = self.py_imports + b"""
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
        self.assertRaisesCheckMessage(RecursionTooDeepError, u"one",
                                      self.ch.reply, "local", {}, u"one")

    def test_Reply_RespondsCorrectly_ToTwoUsers(self):
        py = self.py_imports + b"""
class TestScript(Script):
    @rule("my name is _@~3")
    def rule_name(self):
        self.uservars["name"] = self.match["raw_match0"]
        return "Nice to meet you!"
    @rule("what did you just say", previous_reply="_*")
    def rule_what(self):
        return 'I just said "{raw_reply_match0}"'
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
            (u"one", u"What did you just say?",
                     u'I just said "Nice to meet you!"'),
            (u"two", u"My name is Test Two", u"Nice to meet you!"),
            (u"one", u"What is my name?", u"Your name is Test One.")]
        self.have_conversation(py, conversation)

    def test_Reply_LimitsRuleSelectionByTopic(self):
        py = self.py_imports + b"""
class TestScriptMain(Script):
    @rule("change topic")
    def rule_change_topic(self):
        self.current_topic = "test"
        return "changed to test"
    @rule("topic")
    def rule_topic(self):
        return "all star"

class TestScriptTest(Script):
    topic = "test"
    @rule("change topic")
    def rule_change_topic(self):
        self.current_topic = "all"
        return "changed to all"
    @rule("topic")
    def rule_topic(self):
        return "test star"
"""
        conversation = [(0, u"topic", u"all star"),
                        (0, u"change topic", u"changed to test"),
                        (0, u"topic", u"test star"),
                        (0, u"change topic", u"changed to all"),
                        (0, u"topic", u"all star")]
        self.have_conversation(py, conversation)

    def test_Reply_CallsSubstitutionsByTopic(self):
        py = self.py_imports + b"""
class TestScriptMain(Script):
    def substitute(self, text, wordlists):
        sub = {"3":"three"}
        return [[sub.get(w, w) for w in wl] for wl in wordlists]
    @rule("change topic")
    def rule_change_topic(self):
        self.current_topic = "test"
        return "changed to test"
    @rule("1 2 three")
    def rule_topic(self):
        return "pass all"

class TestScriptTest(Script):
    topic = "test"
    def substitute(self, text, wordlists):
        sub = {"1":"one"}
        return [[sub.get(w, w) for w in wl] for wl in wordlists]
    @rule("change topic")
    def rule_change_topic(self):
        self.current_topic = "all"
        return "changed to all"
    @rule("one 2 3")
    def rule_topic(self):
        return "pass test"
"""
        conversation = [(100, u"1 2 3", u"pass all"),
                        (100, u"change topic", u"changed to test"),
                        (100, u"1 2 3", u"pass test"),
                        (100, u"change topic", u"changed to all"),
                        (100, u"1 2 3", u"pass all")]
        self.have_conversation(py, conversation)

    def assertRaisesCheckMessage(self, expected_error, expected_message,
                                 func, *args, **kwargs):
        """ assert that an error is raised, and that something useful is in 
        e.args[0]
        """
        try:
            func(*args, **kwargs)
        except expected_error as e:
            self.assertNotEqual(e.args[0].find(expected_message), "")

    def have_conversation(self, py, conversation):
        self.write_py(py)
        self.ch.load_script_directory(self.scripts_dir)
        for user, msg, rep in conversation:
            self.assertEqual(self.ch.reply(user, {}, msg), rep)
        self.assertFalse(self.errorlogger.called)
        
    def write_py(self, py, filename="test.py"):
        filename = os.path.join(self.scripts_dir, filename)
        with open(filename, "wb") as f:
            f.write(py + b"\n")

if __name__ == "__main__":
    unittest.main()
