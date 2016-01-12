#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Chatbot Reply Generator

"""
from __future__ import print_function
from __future__ import unicode_literals
import collections
import re

from builtins import object, str, zip

from .constants import _HISTORY
from .patterns import Pattern
from .rules import Rule, RulesDB
from .script import Script
from .exceptions import *

#todo use imp thread locking, though this thing is totally not thread-safe
#should force lowercase be an option?

class ChatbotEngine(object):
    """ Python Chatbot Reply Generator

    Loads pattern/reply rules, using a simplified regular expression grammar
    for the patterns, and decorated Python methods for the rules. Maintains
    rules, a variable dictionary for the chatbot's internal state plus one
    for each user conversing with the chatbot. Matches user input to its 
    database of patterns to select a reply rule, which may recursively reference
    other reply patterns and rules.

    Public class methods:
    load_scripts
    reset variables - maybe this should be a flag to load_scripts

    Public instance methods:
    reply
    build_cache -- might be slow, so if you'd prefer to call it during intialization
                  rather than delaying response to first message

    Public instance variables:
        uservars: A dictionary of dictionaries. The outer dictionary is keyed
                  by user_id, which is whatever hashable value you chose to pass 
                  to reply(). Each inner dictionary is simply 
                  variable name:value. Both values are arbitrary, but if you
                  want to be able to reference a variable name in a script
                  pattern, it should begin with a letter, contain only letters,
                  numbers and underscores, and be entirely lower case.
        botvars:  A dictionary of variables similar to the uservars dictionary,
                  but available to scripts interacting with all users of the bot
    """

    def __init__(self, debug=False, depth=50, debuglogger=print,
                 errorlogger=print):
        """Initialize a new ChatbotEngine.

        Keyword arguments: 
        debug -- True or False depending on how much logging you want to see.  
        depth -- Recursion depth limit for replies that reference other replies 
        debuglogger and errorlogger -- functions which will be passed a single 
                  string with debugging or warning message output respectively. 
                  The default is to use print but you can set them to None to 
                  silence output.

        """
        self._debuglogger = debuglogger
        self._errorlogger = errorlogger
        self._depth_limit = depth

        self.botvars = {}
        self.botvars["debug"] = str(debug)
        
        self._variables = {"b" : self.botvars,
                           "u" : None}
        
        self.users = {}
        self.clear_rules()
        
        self._say("Chatbot instance created.")

    def clear_rules(self):
        self.rules_db = RulesDB(self._say)

    def load_script_directory(self, directory):
        self.rules_db.load_script_directory(directory, self.botvars)

    def _say(self, message, warning=""):
        """Print all warnings to the error log, and debug messages to the
        debug log if the debug bot variable is set.

        """
        if warning:
            if self._errorlogger:
                self._errorlogger("[Chatbot {0}] {1}".format(warning,
                                                             message))
        elif (self._variables["b"].get("debug", "False") == "True"
              and self._debuglogger):
            self._debuglogger("[Chatbot] {0}".format(message))

    ##### Reading scripts and building the database of rules #####

    
    def reply(self, user, message):
        """ For the current topic, find the best matching rule for the message.
        Recurse as necessary if the first rule returns references to other 
        rules. 

        Exceptions:
        RecursionTooDeepError -- if recursion goes over depth limit passed
            to __init__
        """
        self.rules_db.sort_rules()
        self._say('Asked to reply to: "{0}" from {1}'.format(message, user))
        self._set_user(user)
        Script.botvars = self.botvars
        if not isinstance(message, str):
            print(str(type(message)))
            raise TypeError("message argument must be unicode, not str")

        reply = self._reply(user, message, 0)
        self.users[user].msg_history.appendleft(message)
        self.users[user].repl_history.appendleft(Target(reply, say=self._say))
        return reply

    def _reply(self, user, message, depth):
        if depth > self._depth_limit:
            raise RecursionTooDeepError
        self._say('Searching for rule matching "{0}", depth == {1}'.format(
            message, depth))
        
        target = Target(message, say=self._say)
        reply = ""
        topic = self.users[user].vars["__topic__"]
        for rule in self.rules_db.topics[topic].sortedrules:
            m = rule.match(target, self.users[user].repl_history,
                           self._variables)
            if m is not None:
                self._say("Found match, rule {0}".format(
                    rule.rulename))
                Script.match = m.dict
                reply = rule.method()
                if not isinstance(reply, str):
                    raise TypeError("Rule {0} returned something other than a "
                                    "unicode string.".format(rule.rulename))
                self._say('Rule {0} returned "{1}"'.format(
                    rule.rulename, reply))
                if Script.current_topic != topic:
                    if Script.current_topic not in self.rules_db.topics:
                        self._say("Rule {0} changed to empty topic {1}, "
                                  "returning to 'all'".format(rule.rulename,
                                                              topic),
                                  warning="Warning")
                    else:
                        topic = Script.current_topic
                        self.users[user].vars["__topic__"] = topic
                        self._say("User {0} now in topic {1}".format(user,
                                                                     topic))

                break

        reply = self._recursively_expand_reply(user, m, reply, depth)

        if not reply:
            self._say("Empty reply generated")
        else:
            self._say("Generated reply: " + reply)
        return reply

    def _recursively_expand_reply(self, user, m, reply, depth):
        matches = [m for m in re.finditer("<.*?>", reply, flags=re.UNICODE)]
        if matches:
            self._say("Rule returned: " + reply)
        sub_replies = []
        for match in matches:
            begin, end = match.span()
            rep = self._reply(user, reply[begin + 1:end - 1], depth + 1)
            sub_replies.append(rep)
        zipper = list(zip(matches, sub_replies))
        zipper.reverse()
        for match, rep in zipper:
            begin, end = match.span()
            reply = reply[:begin] + rep + reply[end:]
        return reply    
        

    def _set_user(self, user):
        new = False
        if user not in self.users:
            self.users[user] = UserInfo()
            new = True
        uservars = self.users[user].vars
        
        topic = uservars["__topic__"]
        if topic not in self.rules_db.topics:
            self._say("User {0} is in empty topic {1}, "
                      "returning to 'all'".format(user, topic))
            topic = uservars["__topic__"] = "all"

        Script.set_user(user, uservars)
        self._variables["u"] = uservars

        if new:
            for inst in self.rules_db.script_instances:
                inst.setup_user(user)
            
class UserInfo(object):
    def __init__(self):
        self.vars = {}
        self.vars["__topic__"] = "all"
        self.msg_history = collections.deque(maxlen=_HISTORY)
        self.repl_history = collections.deque(maxlen=_HISTORY)

    
class Target(object):
    """ Prepare a message to be a match target.
    - Break it into a list of words on whitespace and save the originals
    - lowercase everything
    - Run substitutions
    - Kill remaining non-alphanumeric characters

    Public instance variables:
    raw_text: the string passed to the constructor
    raw_words: a list of words of the same string, split on whitespace
    tokenized_words: a list of lists, one for each word in orig_words
        after making them lower case, doing substitutions (see below),
        and removing all remaining non-alphanumeric characters.
        
    normalized: tokenized_words, joined back together by single spaces

    For example, given that "i'm" => "i am" and "," => "comma" are in the 
    substitutions list, here are the resulting values of raw_words,
    tokenized_words, and normalized:

    I'm tired today! ==>  ["I'm", "tired", "today!"],
                          [["i", "am"], ["tired"], ["today"]]
                          "i am tired today"
    Bob's cat is missing. ==> ["Bob's", "cat", "is", "missing."]
                              [["bob", "s"], ["cat"], ["is"], ["missing"]]
                              "bob s cat is missing"
    Wazzup! :) ==> ["Wazzup!", ":)"]
                   [["wazzup"], [""]])
                   "wazzup"
    I need bacon, eggs and milk. ==> ["I", "need", "bacon,", "eggs", 
                                      "and", "milk."]
                                     [["i"], ["need"], ["bacon", "comma"],
                                      ["eggs"], ["and"], ["milk"]]
                                     "i need bacon comma eggs and milk"
    """
    def __init__(self, text, substitutions=None, say=print):
        self.raw_text = text
        self.raw_words = self.split_on_spaces(text)
        self.lc_words = [word.lower() for word in self.raw_words]
        self.sub_words = [self._do_substitutions(word, substitutions)
                          for word in self.lc_words]
        self.tokenized_words = [[self._kill_non_alphanumerics(word)
                        for word in wl] for wl in self.sub_words]
        self.normalized = " ".join(
                                [" ".join(wl) for wl in self.tokenized_words])
        if say == None:
            say = lambda s:s
        self._say = say
        self._say('[Target] Normalized message to "{0}"'.format(self.normalized))

    def split_on_spaces(self, text):
        """ Because this has to work in Py 2.6, and re.split doesn't do UNICODE
        in 2.6.  Return text broken into words by whitespace. """
        matches = [m for m in re.finditer("[\S]+", text, flags=re.UNICODE)]
        results = [text[m.span()[0]:m.span()[1]] for m in matches]
        return results

    def _do_substitutions(self, word, substitutions):
        """Check a word against the substitutions dictionary. If the word is
        not found, return it wrapped in a list. Otherwise return the
        value from the dictionary as a list of words.
        """
        if substitutions is None:
            return [word]
        else:
            replacement = self._substitutions.get(word, word)
            return re.split('\s+', replacement, flags=re.UNICODE)

    def _kill_non_alphanumerics(self, text):
        """remove any non-alphanumeric characters from a string and return the
        result. re.sub doesn't do UNICODE in python 2.6.

        """
        matches = [m for m in re.finditer("[\w]+", text, flags=re.UNICODE)]
        result = "".join([text[m.span()[0]:m.span()[1]] for m in matches])
        return result        
            

