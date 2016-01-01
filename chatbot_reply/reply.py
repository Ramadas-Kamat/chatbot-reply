#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Chatbot Reply Generator

"""

from __future__ import print_function
import imp
import inspect
import os
import re
import traceback

from .patterns import PatternParser
from .exceptions import PatternError, PatternVariableNotFoundError
from .exceptions import PatternMethodSpecError, RecursionTooDeepError
from .exceptions import NoRulesFoundError
from .script import Script, ScriptRegistrar

#strict: making it an option to throw errors instead of ignoring them
#todo use imp thread locking, though this thing is totally not thread-safe
#should force lowercase be an option?
# load_directory or load_script_directory, all the loading code needs work
# the topic database should be its own class
# weights for previous
# match0 and botmatch0
# recursion


class ChatbotEngine(object):
    """ Python Chatbot Reply Generator

    Loads pattern/reply rules, using a simplified regular expression grammar
    for the patterns, and decorated Python methods for the rules. Maintains
    rules, a variable dictionary for the chatbot's internal state plus one
    for each user conversing with the chatbot. Matches user input to its 
    database of patterns to select a reply rule, which may recursively reference
    other reply patterns and rules.

    How script loading works. How multiple instances of Chatbot have to share.

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
        self._botvars = {"debug":unicode(debug)}
        
        self._PREFIX = "________" # added to script module names to avoid 
                                  # namespace conflicts

        self._uservars = {}
        self._substitutions = {}
        self.clear_rules()
        self._parser = PatternParser()
        
        self._say("Chatbot instance created.")


    def _say(self, message, warning=""):
        """Print all warnings to the error log, and debug messages to the
        debug log if the debug bot variable is set.

        """
        if warning:
            if self._errorlogger:
                self._errorlogger("[Chatbot {0}] {1}".format(warning,
                                                             message))
        elif self._botvars.get("debug", "False") == "True" and self._debuglogger:
            self._debuglogger("[Chatbot] {0}".format(message))

    ##### Reading scripts and building the database of rules #####
    
    def load_script_directory(self, directory):
        """Iterate through the .py files in a directory, and import all of
        them. Then look for subclasses of Script and search them for
        rules, and load those into self._topics.

        """
        self.cache_built = False
        ScriptRegistrar.clear()
        
        for item in os.listdir(directory):
            if item.lower().endswith(".py"):
                filename = os.path.join(directory, item)
                self._import(filename)


        Script.botvars = self._botvars

        for cls in ScriptRegistrar.registry:
            self._say("Loading scripts from" + cls.__name__)
            self._load_script(cls)

        if sum([len(t.rules) for k, t in self._topics.items()]) == 0:
            raise NoRulesFoundError(
                "No rules were found in {0}/*.py".format(directory))
                
    def _import(self, filename):
        """Import a python module, given the filename, but to avoid creating
        namespace conflicts give the module a name consisting of
        _PREFIX + filename (minus any extension).

        """
        path, name = os.path.split(filename)
        name, ext = os.path.splitext(name)

        self._say("Reading " + filename)
        modname = self._PREFIX + name
        file, filename, data = imp.find_module(name, [path])
        mod = imp.load_module(modname, file, filename, data)
        return mod

    def _load_script(self, script_class):
        """Given a subclass of Script, create an instance of it, then
        find all of its methods which begin with one of our keywords
        and add them to the topic database

        """
        dispatch = [("pattern", self._load_pattern),
                    ("substitute", self._load_substitute)]

        instance = script_class()
        script_class_name = (instance.__module__[len(self._PREFIX):] + "." +
                             instance.__class__.__name__)
        
        topic = instance.topic
        if topic == None: #this is the way to define a script superclass
            return
        if topic not in self._topics:
            self._new_topic(topic)

        alternates = {}
        if hasattr(instance, "alternates"):
            try:
                alternates = Rule.validate_alternates(instance.alternates,
                                                      script_class_name)
            except PatternError as e:
                e.args += (" in self.alternates of " + script_class_name,)
                raise
        
        for attribute in dir(instance):
            for name, func in dispatch:
                if (attribute.startswith(name) and
                    hasattr(getattr(instance, attribute), '__call__')):
                    func(topic, script_class_name, instance, attribute, alternates)

    def clear_rules(self):
        self._topics = {}
        self._new_topic("all")
        
    def _new_topic(self, topic):
        self._topics[topic] = Topic()
    
    def _load_pattern(self, topic, script_class_name, instance, attribute,
                      alternates):
        method = getattr(instance, attribute)
        argspec = inspect.getargspec(method)
        rulename = script_class_name + "." + attribute

        if self._check_pattern_spec(rulename, argspec):
            raw_pattern, raw_previous, weight = argspec.defaults
            rule = Rule(raw_pattern, raw_previous, weight, alternates,
                            method, rulename, say=self._say)
            tup = (rule.formatted_pattern, rule.formatted_previous)
            if tup in self._topics[topic].rules:
                existing_rule = self._topics[topic].rules[tup]
                if method != existing_rule.rule:
                    self._say('Ignoring pattern "{0}","{1}" at {2} because it '
                              'is a duplicate of the pattern of {3} '
                              'for the topic "{4}".'.format(
                                  raw_pattern, raw_previous, rulename,
                                  existing_rule.rulename, topic),
                              warning = "Warning")
            else:
                self._topics[topic].rules[tup] = rule
                self._say('Loaded pattern "{0}", previous="{1}", weight={2}, '
                          'method = {3}'.format(raw_pattern, raw_previous,
                                                weight, attribute))

    def _check_pattern_spec(self, name, argspec):
        """ Check that the passed argument spec matches what we expect the
        @pattern decorator in scripts.py to do. Prints an error
        message and returns false if a problem is found, otherwise
        returns True. The name and func arguments are only used to
        make a better error message.  """
        if (len(argspec.args) != 4 or
            " ".join(argspec.args) != "self pattern previous weight" or
            argspec.varargs is not None or
            argspec.keywords is not None or
            len(argspec.defaults) != 3):
            raise PatternMethodSpecError("{0} was not decorated by @pattern "
                     "or it has the wrong number of arguments".format(name))
        return True

    
    def _load_substitute(self, topic, script_class, attribute):
        pass

    def build_cache(self):
        if self.cache_built:
            return
        for n, t in self._topics.items():
            t.sortedrules = sorted([rule for key, rule in t.rules.items()],
                                   reverse=True)
            for rule in t.sortedrules:
                rule.cache_regexes()
        self.cache_built = True

    
    def reply(self, user, message, depth=0):
        if depth == 0:
            self.build_cache()
            self._say('Asked to reply to: "{0}" from {1}'.format(message,
                                                                 unicode(user)))
            self._set_user(user)
            Script.botvars = self._botvars
        elif depth < self._depth_limit:
            self._say('Recursing to find reply to "{0}", depth == {1}'.format(
                message, depth))
        else:
            raise RecursionTooDeepError
        
        target = Target(message, say=self._say)
        reply = ""
        for rule in self._topics["all"].sortedrules:
            m = re.match(rule.regexc, target.normalized)
            if m is not None:
                self._say("Found pattern match, rule {0}".format(
                    rule.rulename))
                Script.match = self._match_dict(m.groupdict())
                reply = rule.rule()
                break
        if not reply:
            self._say("Empty reply generated")
        return unicode(reply)

    def _set_user(self, user):
        if user not in self._uservars:
            self._uservars[user] = {"__topic__":"all"}
        uservars = self._uservars[user]
        
        topic = uservars["__topic__"]
        if topic not in self._topics:
            self._say("User {0} is in empty topic {1}, "
                      "returning to 'all'".format(unicode(user), topic))
            topic = uservars["__topic__"] = "all"

        Script.set_user(user, uservars)

    def _set_topic(self, user, topic):
        self._uservars[user]["__topic__"] = topic

    def _match_dict(self, re_dict):
        matches = {}
        for k, v in re_dict.items(): #use sorted?
            i = int(k[5:])
            matches[i] = v
        return matches

class Topic(object):
    def __init__(self):
        self.rules = {}
        self.sortedrules = []
    
class Rule(object):
    """ Pattern matching and response rule.

    Describes one method decorated by @pattern (see script.py). Parses
    the simplified regular expression strings, raising an exception
    if there is an error. Can match the pattern and previous_pattern
    against tokenized input (a Target) and return a Match object.

    Public instance variables:
    formatted_pattern - the pattern reformatted by the parser for
                        more accurate comparisons
    formatted_previous - the previous_pattern, reformatted by the parser
    weight             - the weight, given to @pattern
    alternates         - a dictionary 
    rule               - a reference to the decorated method
    rulename           - classname.methodname, for error messages
    score              - a calculated score based on the amount of 
                        actual words (not wildcards) in the pattern

    Public methods:
    cache_regexes --
    match -- returns match object if it does
    full set of comparison operators - to enable sorting first by weight then 
            score
    """
    _pp = PatternParser()
    
    def __init__(self, raw_pattern, raw_previous, weight, alternates,
                 rule, rulename, say=lambda s: None):
        self._say = say
        try:
            self._pattern_tree = self.__class__._pp.parse(raw_pattern)
        except PatternError as e:
            e.args += (" in pattern of {0}.".format(rulename),)
            raise
        if raw_previous != "":
            try:
                self._previous_tree = self.__class__._pp.parse(raw_previous)
            except PatternError as e:
                e.args += (" in previous pattern of {0}.".format(rulename),)
                raise
        else:
            self._previous_tree = None    
        
        self.weight = weight
        self.alternates = alternates
        self.rule = rule
        self.rulename = rulename
        self.formatted_pattern = self.__class__._pp.format(self._pattern_tree)
        self.formatted_previous = None
        if self._previous_tree is not None:
            self.__class__._pp.format(self._previous_tree)            
        self.score = self.__class__._pp.score(self._pattern_tree)
        self.pattern_regexc = None
        self.previous_regexc = None

    def cache_regexes(self):
        self.pattern_regexc = self._get_regexc(self._pattern_tree,
                                               self.alternates)
        self.previous_regexc = self._get_regexc(self._previous_tree,
                                                self.alternates)
        
    def _get_regexc(self, parsetree, alternates):
        try:
            self.regexc = re.compile(
                self.__class__._pp.regex(self._pattern_tree, alternates) + "$",
                re.UNICODE)
        except PatternVariableNotFoundError:
            self._say("[Rule] Failed to cache regex for {0}.".format(
                self.formatted_pattern))
            return None

    def __lt__(self, other):
        return (self.weight < other.weight or
                (self.weight == other.weight and self.score < other.score))
    def __eq__(self, other):
        return self.weight == other.weight and self.score == other.score
    def __gt__(self, other):
        return (self.weight > other.weight or
                (self.weight == other.weight and self.score > other.score))
    def __le__(self, other):
        return self < other or self == other
    def __ge__(self, other):
        return self > other or self == other
    def __ne__(self, other):
        return not self == other

    @classmethod
    def validate_alternates(cls, alternates, script_class_name):
        valid = {}
        for k, v in alternates.items():
            try:
                valid[k] = cls._pp.format(cls._pp.parse(v, simple=True))
            except PatternError as e:
                e.args += (' in alternates["{0}"] '
                           'of {1}.'.format(k, script_class_name),)
                raise
        return {"a":valid}

    
class Target(object):
    """ Prepare a message to be a match target.
    - Break it into a list of words on whitespace and save the originals
    - lowercase everything
    - Run substitutions
    - Kill remaining non-alphanumeric characters

    Public instance variables:
    orig_text: the string passed to the constructor
    orig_words: a list of words of the same string, split on whitespace
    tokenized_words: a list of lists, one for each word in orig_words
        after making them lower case, doing substitutions (see below),
        and removing all remaining non-alphanumeric characters.
        
    normalized: tokenized_words, joined back together by single spaces

    For example, given that "i'm" => "i am" and "," => "comma" are in the 
    substitutions list, here are the resulting values of orig_words,
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
    def __init__(self, text, substitutions=None, say=lambda s: None):
        self.orig_text = text
        self.orig_words = re.split('\s+', text, re.UNICODE)
        lc_words = [word.lower() for word in self.orig_words]
        sub_words = [self._do_substitutions(word, substitutions)
                     for word in lc_words]
        self.tokenized_words = [[self._kill_non_alphanumerics(word)
                        for word in wl] for wl in sub_words]
        self.normalized = " ".join([" ".join(wl) for wl in self.tokenized_words])
        self._say = say
        self._say('[Target] Normalized message to "{0}"'.format(self.normalized))


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

    def _kill_non_alphanumerics(self, word):
        """remove any non-alphanumeric characters from a string and return the
        result

        """
        return re.sub("[\W]+", "", word, re.UNICODE)
