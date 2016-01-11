#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" chatbot_reply.rules, loads rules from python files
"""
from __future__ import print_function
from __future__ import unicode_literals

import bisect
import imp
import inspect
import os

from .constants import _PREFIX
from .exceptions import *
from .patterns import Pattern
from .script import Script, ScriptRegistrar

class Topic(object):
    def __init__(self):
        self.rules = {}
        self.sortedrules = []

class Rule(object):
    """ Pattern matching and response rule.

    Describes one method decorated by @rule. Parses
    the simplified regular expression strings, raising PatternError
    if there is an error. Can match the pattern and previous_pattern
    against tokenized input (a Target) and return a Match object.

    Public instance variables:
    pattern - the Pattern object to match against the current message
    previous - the Pattern object to match against the previous reply
    weight - the weight, given to @rule
    method - a reference to the decorated method
    rulename - modulename.classname.methodname, for error messages

    Public methods:
    match - given current message and reply history, return a Match
            object if the patterns match or None if they don't
    full set of comparison operators - to enable sorting first by weight then 
            score of the two patterns
    """
    def __init__(self, raw_pattern, raw_previous, weight, alternates,
                 method, rulename, say=print):
        """ Create a new Rule object based on information supplied to the
        @rule decorator. Arguments:
        raw_pattern - simplified regular expression string supplied to @rule
        raw_previous - simplified regular expression string supplied to @rule
        weight -  weight supplied to @rule
        alternates - dictionary of variable names and values that can
                   be substituted in the patterns
        method - reference to method decorated by @rule
        rulename - modulename.classname.methodname, used to make better
                 error messages
        say - a function that takes a string, for debug output. Or None.

        Raises PatternError, PatternVariableNotFoundError, 
               PatternVariableValueError
        """
        try:
            previous = ""
            if not raw_pattern:
                raise PatternError("Empty string found")
            self.pattern = Pattern(raw_pattern, alternates, say=say)
            previous = "previous "
            self.previous = Pattern(raw_previous, alternates, say=say)
        except (PatternError, PatternVariableValueError,\
               PatternVariableNotFoundError) as e: 
            msg = " in {0}pattern of {1}".format(previous, rulename)
            e.args = (e.args[0] + msg,) + e.args[1:]
            raise

        self.weight = weight
        self.method = method
        self.rulename = rulename
        if say is None:
            say = lambda s:s
        self._say = say

    def match(self, target, history, variables):
        """ Return a Match object if the targets match the patterns
        for this rule, or None if they don't.
        Arguments:
            target - a Target object for the user's message
            history - a deque object containing Targets for previous
                      replies
            variables - User and Bot variables for the PatternParser
                      to substitute into the patterns
        """
        m = self.pattern.match(target.normalized, variables)

        if m is None:
            return None
        mp = None
        reply_target = None
        if self.previous:
            if not history:
                return None
            reply_target = history[0]
            mp = self.previous.match(reply_target.normalized, variables)
            if mp is None:
                return None
        return Match(m, mp, target, reply_target)

    def __lt__(self, other):
        return (self.weight < other.weight
                or
                (self.weight == other.weight
                 and self.pattern.score < other.pattern.score)
                or
                (self.weight == other.weight
                 and self.pattern.score == other.pattern.score
                 and self.previous.score < other.previous.score))
                
    def __eq__(self, other):
        return (self.weight == other.weight
                and self.pattern.score == other.pattern.score
                and self.previous.score == other.previous.score)

    def __gt__(self, other):
        return not (self == other or self < other)
    def __le__(self, other):
        return self < other or self == other
    def __ge__(self, other):
        return self > other or self == other
    def __ne__(self, other):
        return not self == other


class Match(object):
    """ dictionary
    match0..matchn - memorized matches
    botmatch0...botmatchn -- matches in the previous reply
    raw_match0..rawn -- untokenized text
    bot_orig0 --
    """
    def __init__(self, m_pattern, m_previous, target, previous_target, say=None):
        self.dict = {}
        self._add_matches(m_pattern, target, "")
        if m_previous is not None:
            self._add_matches(m_previous, previous_target, "bot")

    def _add_matches(self, m, target, prefix):
        offsets = []
        offset = 0
        for wl in target.tokenized_words:
            offsets.append(offset)
            offset += len(" ".join(wl)) + 1
            
        for k, v in m.groupdict().items():
            self.dict[prefix + k] = v
            start, end = m.span(k)
            i_start = bisect.bisect_left(offsets, start)
            i_end = bisect.bisect(offsets, end)
            self.dict["raw_" + prefix + k] = " ".join(target.raw_words[i_start:
                                                                       i_end])

class RulesDB(object):
    def __init__(self, say=print):
        self.clear_rules()
        if say is None:
            say = lambda s:s
        self._say = say

    def clear_rules(self):
        """ Make a fresh new empty rules database. """
        self.topics = {}
        self.script_instances = []
        self._new_topic("all")

    def _new_topic(self, topic):
        """ Add a new topic to the rules database. """
        self.topics[topic] = Topic()
 
    def load_script_directory(self, directory, botvars):
        """Iterate through the .py files in a directory, and import all of
        them. Then look for subclasses of Script and search them for
        rules, and load those into self.topics.
        botvars is a dictionary that loaded scripts can use to initialize
        chatobt state

        """
        self.rules_sorted = False
        ScriptRegistrar.clear()
        Script.botvars = botvars
        
        for item in os.listdir(directory):
            if item.lower().endswith(".py"):
                self._say("Importing " + item)
                filename = os.path.join(directory, item)
                self._import(filename)

        for cls in ScriptRegistrar.registry:
            self._say("Loading scripts from" + cls.__name__)
            self._load_script(cls)

        if sum([len(t.rules) for k, t in self.topics.items()]) == 0:
            raise NoRulesFoundError(
                "No rules were found in {0}/*.py".format(directory))
                
    def _import(self, filename):
        """Import a python module, given the filename, but to avoid creating
        namespace conflicts give the module a name consisting of
        _PREFIX + filename (minus any extension). 
        """
        global _PREFIX
        path, name = os.path.split(filename)
        name, ext = os.path.splitext(name)

        self._say("Reading " + filename)
        modname = _PREFIX + name
        file, filename, data = imp.find_module(name, [path])
        mod = imp.load_module(modname, file, filename, data)
        return mod


    def _load_script(self, script_class):
        topic, rules = self._load_script_class(script_class)
        if topic == None:
            return
        if topic not in self.topics:
            self._new_topic(topic)

        for rule in rules:
            tup = (rule.pattern.formatted_pattern,
                   rule.previous.formatted_pattern)
            if tup in self.topics[topic].rules:
                existing_rule = self.topics[topic].rules[tup]
                if rule.method != existing_rule.method:
                    self._say('Ignoring rule "{0[0]}","{0[1]}" at {1} '
                              'because it is a duplicate of the rule {2} '
                              'for the topic "{3}".'.format(tup,
                              rule.rulename, existing_rule.rulename, topic),
                          warning = "Warning")
            else:
                self.topics[topic].rules[tup] = rule
                self._say('Loaded pattern "{0[0]}", previous="{0[1]}", ' 
                          'weight={1}, method={2}'.format(tup, rule.weight,
                                                           rule.rulename))
           

    def _load_script_class(self, script_class):
        """Given a subclass of Script, create an instance of it,
        find all of its methods which begin with one of our keywords
        and add them to the rules database for the topic of the 
        script instance.

        If the instance defines an alternates dictionary, substitute
        those into the patterns of the rules.

        """
        global _PREFIX
        instance = script_class()
        instance.setup()
        self.script_instances.append(instance)
        script_class_name = (instance.__module__[len(_PREFIX):] + "." +
                             instance.__class__.__name__)
        
        topic = instance.topic
        if topic == None: #this is the way to define a script superclass
            return None, []
        if topic not in self.topics:
            self._new_topic(topic)

        alternates = {}
        if hasattr(instance, "alternates"):
            alternates = self._validate_alternates(instance.alternates,
                                                   script_class_name)
        rules = []
        for attribute in dir(instance):
            if attribute.startswith('rule'):
                rule = self._load_rule(topic, script_class_name, instance,
                                       attribute, alternates)
                rules.append(rule)
        return topic, rules

   
    def _validate_alternates(self, alternates, script_class_name):
        if not isinstance(alternates, dict):
            raise InvalidAlternatesError(
                "self.alternates is not a dictionary in {0}.".format(
                    script_class_name))
        valid = {}
        for k, v in alternates.items():
            if not (isinstance(k, unicode) and isinstance(v, unicode)):
                raise TypeError("self.alternates contains non-unicode strings "
                                "in {0}".format(script_class_name))
            try:
                valid[k] = Pattern(v, simple=True,
                                   say=self._say).formatted_pattern
            except PatternError as e: 
                msg = ' in alternates["{0}"] of {1}'.format(k,
                                                             script_class_name)
                e.args = (e.args[0] + msg,) + e.args[1:]
                raise
        return {"a":valid}

    def _load_rule(self, topic, script_class_name, instance, attribute,
                      alternates):
        """ Given an instance of a class derived from Script and
        a callable attribute, check that it is declared correctly, 
        and then add it to the rules database for the given topic.
        """
        method = getattr(instance, attribute)
        rulename = script_class_name + "." + attribute

        argspec = get_rule_method_spec(rulename, method)

        raw_pattern, raw_previous, weight = argspec.defaults
        if not (isinstance(raw_pattern, unicode) and
                isinstance(raw_previous, unicode)):
            raise TypeError("@rule given non-unicode string in {0}".format(
                rulename))
        return Rule(raw_pattern, raw_previous, weight, alternates,
                    method, rulename, say=self._say)

    def _load_substitute(self, topic, script_class, attribute):
        pass

    def sort_rules(self):
        """ Sort the rules for each topic """
        if self.rules_sorted:
            return
        for n, t in self.topics.items():
            t.sortedrules = sorted([rule for key, rule in t.rules.items()],
                                   reverse=True)
        self.rules_sorted = True
        self._say("-"*20 + "Sorted rules" + "-"*20)
        for n, t in self.topics.items():
            self._say("Topic: {0}".format(n))
            for r in t.sortedrules:
                self._say('"{0}"/"{1}"'.format(r.pattern.formatted_pattern,
                                               r.previous.formatted_pattern))
        self._say("-"*52)

    

        
def get_rule_method_spec(name, method):
    """ Check that the passed argument spec matches what we expect the
    @rule decorator in scripts.py to do. Raises RuleMethodSpecError
    if a problem is found. If all is good, return the argspec
    (see inspect.getargspec)
    """
    if not hasattr(method, '__call__'):
        raise RuleMethodSpecError(
            "{0} begins with 'rule' but is not callable.".format(
                name))
    argspec = inspect.getargspec(method)
    if (len(argspec.args) != 4 or
        " ".join(argspec.args) != "self pattern previous weight" or
        argspec.varargs is not None or
        argspec.keywords is not None or
        len(argspec.defaults) != 3):
        raise RuleMethodSpecError("{0} was not decorated by @rule "
                 "or it has the wrong number of arguments.".format(name))
    return argspec

