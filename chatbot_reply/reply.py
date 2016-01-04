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

from codecs import BOM_UTF8

from .patterns import PatternParser
from .exceptions import *
from .script import Script, ScriptRegistrar, get_method_spec

#todo use imp thread locking, though this thing is totally not thread-safe
#should force lowercase be an option?
# the topic database should be its own class
# the pattern parser should be a class attribute of Pattern
# dict subclass that makes everything be unicode
# Script.alternates should use that
# in load_rule convert things to unicode
# after that PatternParser can assert everything is unicode
# need a class for variable dictionaries


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
        self._history = History(10)
        self.clear_rules()

        self._encoding = None
        self._pp = PatternParser()
        
        self._say("Chatbot instance created.")


    def _say(self, message, warning=""):
        """Print all warnings to the error log, and debug messages to the
        debug log if the debug bot variable is set.

        """
        if warning:
            if self._errorlogger:
                self._errorlogger(u"[Chatbot {0}] {1}".format(warning,
                                                             message))
        elif self._botvars.get("debug", "False") == "True" and self._debuglogger:
            self._debuglogger(u"[Chatbot] {0}".format(message))

    ##### Reading scripts and building the database of rules #####

    def clear_rules(self):
        """ Make a fresh new empty rules database. """
        self._topics = {}
        self._new_topic("all")
        # it would be prudent to unicodify any str's in the variables
        self._encoding = None
        
    def _new_topic(self, topic):
        """ Add a new topic to the rules database. """
        self._topics[topic] = Topic()
 
    
    def load_script_directory(self, directory):
        """Iterate through the .py files in a directory, and import all of
        them. Then look for subclasses of Script and search them for
        rules, and load those into self._topics.

        """
        self.cache_built = False
        ScriptRegistrar.clear()
        Script.botvars = self._botvars
        
        for item in os.listdir(directory):
            if item.lower().endswith(".py"):
                self._say("Importing " + item)
                filename = os.path.join(directory, item)
                self._import(filename)

        self._pp.encoding = self._encoding
        for cls in ScriptRegistrar.registry:
            self._say("Loading scripts from" + cls.__name__)
            self._load_script(cls)

        if sum([len(t.rules) for k, t in self._topics.items()]) == 0:
            raise NoRulesFoundError(
                u"No rules were found in {0}/*.py".format(directory))
                
    def _import(self, filename):
        """Import a python module, given the filename, but to avoid creating
        namespace conflicts give the module a name consisting of
        _PREFIX + filename (minus any extension). Also check that the 
        source file encoding doesn't conflict with anything we've already
        loaded.

        """
        path, name = os.path.split(filename)
        name, ext = os.path.splitext(name)

        self._say("Reading " + filename)
        modname = self._PREFIX + name
        file, filename, data = imp.find_module(name, [path])
        mod = imp.load_module(modname, file, filename, data)
        self._check_encodings(filename)
        return mod

    def _check_encodings(self, filename):
        """Given the filename of a Python source file, that's already been
        successfully imported by the interpreter, determine it's
        source encoding by reading the first two lines and looking for
        either the BOM_UTF8 or the encoding cookie comment. If it
        doesn't match the encoding of any file we've previously read
        raise a MismatchedEncodingsError, otherwise remember it to
        check against the next file.

        """
        with open(filename, "r") as f:
            encoding = self._detect_encoding(f.readline)
        if self._encoding == None:
            self._encoding = encoding
            self._encoding_filename = filename
        elif encoding != self._encoding:
            raise MismatchedEncodingsError(
                u"All script files must use the same source encoding. "
                u"{0} is using {1} and {2} is using {3}.".format(
                    self._encoding_filename, self._encoding, filename, encoding))

    def _detect_encoding(self, readline):
        """Detect the encoding that is used in a Python source file. Based on
        tokenize.py from Python 3.2, simplified a bit because we can
        assume there are no errors, because the file already was
        successfully loaded by the Python interpreter.

        It will call readline a maximum of twice, and return the
        encoding used (as a string).

        It detects the encoding from the presence of a utf-8 bom or an
        encoding cookie as specified in pep-0263. If none is found, it
        will return utf-8.

        """
        default = 'utf-8'
        def read_or_stop():
            try:
                return readline()
            except StopIteration:
                return ""

        def find_cookie(line):
            # Decode as UTF-8. Either the line is an encoding declaration,
            # in which case it should be pure ASCII, or it must be UTF-8
            # per default encoding.
            line_string = line.decode('utf-8')
            matches = re.findall("coding[:=]\s*([-\w.]+)", line_string)
            if not matches:
                return None
            encoding = get_normal_name(matches[0])
            return encoding

        def get_normal_name(orig_enc):
            # Only care about the first 12 characters.
            enc = orig_enc[:12].lower().replace("_", "-")
            if enc == "utf-8" or enc.startswith("utf-8-"):
                return "utf-8"
            if enc in ("latin-1", "iso-8859-1", "iso-latin-1") or \
               enc.startswith(("latin-1-", "iso-8859-1-", "iso-latin-1-")):
                return "iso-8859-1"
            return orig_enc

        first = read_or_stop()
        if not first or first.startswith(BOM_UTF8):
            return default

        encoding = find_cookie(first)
        if encoding:
            return encoding

        second = read_or_stop()
        if not second:
            return default

        encoding = find_cookie(second)
        if encoding:
            return encoding

        return default

    def _load_script(self, script_class):
        """Given a subclass of Script, create an instance of it,
        find all of its methods which begin with one of our keywords
        and add them to the rules database for the topic of the 
        script instance.

        If the instance defines an alternates dictionary, substitute
        those into the patterns of the rules.

        """
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
            alternates = self._validate_alternates(instance.alternates,
                                                   script_class_name)
        
        for attribute in dir(instance):
            if attribute.startswith('pattern'):
                self._load_rule(topic, script_class_name, instance, attribute,
                          alternates)

   
    def _validate_alternates(self, alternates, script_class_name):
        if not isinstance(alternates, dict):
            raise InvalidAlternatesError(
                u"self.alternates is not a dictionary in {0}.".format(
                    script_class_name))
        valid = {}
        for k, v in alternates.items():
            try:
                valid[k] = self._pp.format(self._pp.parse(str(v),
                                                          simple=True))
            except PatternError as e:
                e.args += (u' in alternates["{0}"] '
                           'of {1}.'.format(unicode(k, self._encoding),
                                            script_class_name),)
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

        argspec = get_method_spec(rulename, method)

        raw_pattern, raw_previous, weight = argspec.defaults
        rule = Rule(self._pp, raw_pattern, raw_previous, weight, alternates,
                    method, rulename, say=self._say)
        tup = (rule.pattern.formatted_pattern, rule.previous.formatted_pattern)
        if tup in self._topics[topic].rules:
            existing_rule = self._topics[topic].rules[tup]
            if method != existing_rule.method:
                self._say(u'Ignoring pattern "{0[0]}","{0[1]}" at {1} '
                          u'because it is a duplicate of the pattern of {2} '
                          u'for the topic "{3}".'.format(tup,
                              rulename, existing_rule.rulename, topic),
                          warning = "Warning")
        else:
            self._topics[topic].rules[tup] = rule
            self._say(u'Loaded pattern "{0[0]}", previous="{0[1]}", ' 
                      u'weight={1}, method={2}'.format(tup, weight,
                                                         attribute))

    def _load_substitute(self, topic, script_class, attribute):
        pass

    def build_cache(self):
        """ Sort the rules for each topic """
        if self.cache_built:
            return
        for n, t in self._topics.items():
            t.sortedrules = sorted([rule for key, rule in t.rules.items()],
                                   reverse=True)
        self.cache_built = True
        self._say("-"*20 + "Sorted rules" + "-"*20)
        for r in t.sortedrules:
            self._say('"{0}"/"{1}"'.format(r.pattern.formatted_pattern,
                                           r.previous.formatted_pattern))
        self._say("-"*52)

    
    def reply(self, user, message):
        """ For the current topic, find the best matching rule for the message.
        Recurse as necessary if the first rule returns references to other 
        rules. 

        Exceptions:
        RecursionTooDeepError -- if recursion goes over depth limit passed
            to __init__
        PatternVariableNotFoundError -- if a pattern references a user or bot 
            variable that is not defined
        """
        self.build_cache()
        self._say(u'Asked to reply to: "{0}" from {1}'.format(message, user))
        self._set_user(user)
        Script.botvars = self._botvars
        if not isinstance(message, unicode):
            raise TypeError("message argument must be unicode, not str")

        variables = {"u":Script.uservars, "b":Script.botvars}

        reply = self._reply(user, message, variables, 0)
        self._history.update(message, Target(reply, say=self._say))
        return reply

    def _reply(self, user, message, variables, depth):
        if depth > self._depth_limit:
            raise RecursionTooDeepError
        self._say(u'Trying to find reply to "{0}", depth == {1}'.format(
            message, depth))
        
        target = Target(message, say=self._say)
        reply = ""
        for rule in self._topics["all"].sortedrules:
            m = rule.match(self._pp, target, self._history, variables)
            if m is not None:
                self._say(u"Found pattern match, rule {0}".format(
                    rule.rulename))
                Script.match = m.dict
                reply = rule.method()
                break
        matches = [m for m in re.finditer("<.*?>", reply, flags=re.UNICODE)]
        matches.reverse()
        for m in matches:
            begin, end = m.span()
            rep = self._reply(user, reply[begin + 1:end - 1], variables, depth + 1)
            reply = reply[:begin] + rep + reply[end:]

        if not reply:
            self._say("Empty reply generated")
        else:
            self._say("Generated reply: " + reply)
        return reply

    def _set_user(self, user):
        if user not in self._uservars:
            self._uservars[user] = {"__topic__":"all"}
        uservars = self._uservars[user]
        
        topic = uservars["__topic__"]
        if topic not in self._topics:
            self._say(u"User {0} is in empty topic {1}, "
                      "returning to 'all'".format(user, topic))
            topic = uservars["__topic__"] = "all"

        Script.set_user(user, uservars)

    def _set_topic(self, user, topic):
        self._uservars[user]["__topic__"] = topic

class Topic(object):
    def __init__(self):
        self.rules = {}
        self.sortedrules = []
    
class Pattern(object):
    def __init__(self, pp, raw, alternates, say=print):
        self.raw = raw
        self.alternates = alternates
        self.say = say
        if self.raw:
            self._parse_tree = pp.parse(raw)
            self.formatted_pattern = pp.format(self._parse_tree)
            self.score = pp.score(self._parse_tree)
            self.regexc = self._get_regexc(pp, alternates, say)
        else:
            self._parse_tree = None
            self.formatted_pattern = ""
            self.score = pp.score(pp.parse("*"))
            self.regexc = None

    def __len__(self):
        return len(self.raw)

    def _get_regexc(self, pp, alternates, say):
        try:
            regex = pp.regex(self._parse_tree, alternates) + "$"
            say("Formatted Pattern: {0}, regex = {1}".format(
                self.formatted_pattern, regex))
            return re.compile(regex, flags=re.UNICODE)
        except PatternVariableNotFoundError:
            self._say(u"[Pattern] Failed to cache regex for {0}.".format(
                self.formatted_pattern))
            return None

    def __eq__(self, other):
        return self.formatted_pattern == other.formatted_pattern


class Rule(object):
    """ Pattern matching and response rule.

    Describes one method decorated by @patterns. Parses
    the simplified regular expression strings, raising PatternError
    if there is an error. Can match the pattern and previous_pattern
    against tokenized input (a Target) and return a Match object.

    Public instance variables:
    pattern - the Pattern object to match against the current message
    previous - the Pattern object to match against the previous reply
    weight - the weight, given to @pattern
    method - a reference to the decorated method
    rulename - classname.methodname, for error messages

    Public methods:
    match - given current message and reply history, return a Match
            object if the patterns match or None if they don't
    full set of comparison operators - to enable sorting first by weight then 
            score of the two patterns
    """
    def __init__(self, pp, raw_pattern, raw_previous, weight, alternates,
                 method, rulename, say=print):
        """ Create a new Rule object based on information supplied to the
        @pattern decorator. Arguments:
        pp - a PatternParser object
        raw_pattern - simplified regular expression string (not necessarily 
                      unicode) supplied to @pattern
        raw_previous - simplified regular expression string (not necessarily 
                      unicode)supplied to @pattern
        weight -  weight supplied to @pattern
        alternates - dictionary of variable names and values that can
                   be substituted in the patterns by PatternParser
        method - reference to method decorated by @pattern
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
            self.pattern = Pattern(pp, raw_pattern, alternates, say) 
            previous = "previous "
            self.previous = Pattern(pp, raw_previous, alternates, say)
        except (PatternError, PatternVariableValueError,\
               PatternVariableNotFoundError) as e:
            e.args += (u" in {0}pattern of {1}.".format(previous, rulename),)
            raise
        
        self.weight = weight
        self.method = method
        self.rulename = rulename
        if say is None:
            say = lambda s:s
        self._say = say

    def match(self, pp, target, history, variables):
        """ Return a Match object if the targets match the patterns
        for this rule, or None if they don't.
        Arguments:
            pp - a PatternParser object
            target - a Target object for the user's message
            history - a History object containing Targets for previous
                      messages and replies
            variables - User and Bot variables for the PatternParser
                      to substitute into the patterns
        """
        m = re.match(self.pattern.regexc, target.normalized)
        if m is None:
            return None
        mp = None
        reply_target = None
        if self.previous:
            if not history.replies:
                return None
            reply_target = history.replies[0]
            self._say("[Rule] checking previous {0} vs target {1}".format(
                self.previous.formatted_pattern, reply_target.normalized))
            mp = re.match(self.previous.regexc, reply_target.normalized)
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
    def __init__(self, text, substitutions=None, say=print):
        self.orig_text = text
        self.orig_words = self.split_on_spaces(text)
        self.lc_words = [word.lower() for word in self.orig_words]
        self.sub_words = [self._do_substitutions(word, substitutions)
                          for word in self.lc_words]
        self.tokenized_words = [[self._kill_non_alphanumerics(word)
                        for word in wl] for wl in self.sub_words]
        self.normalized = u" ".join(
                                [u" ".join(wl) for wl in self.tokenized_words])
        if say == None:
            say = lambda s:s
        self._say = say
        self._say(u'[Target] Normalized message to "{0}"'.format(self.normalized))

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
            
class History(object):
    def __init__(self, size):
        self.messages = []
        self.replies = []
        self.size = size
        pass
    def update(self, message, reply):
        if len(self.messages) >= self.size:
            pop(self.messages)
        if len(self.replies) >= self.size:
            pop(self.replies)
        self.messages.insert(0, message)
        self.replies.insert(0, reply)

class Match(object):
    """ dictionary
    match0..matchn - memorized matches
    botmatch0...botmatchn -- matches in the previous reply
    orig0 -- untokenized text
    bot_orig0 --
    """
    def __init__(self, m_pattern, m_previous, target, previous_target, say=None):
        self.dict = {}
        for k, v in m_pattern.groupdict().items():
            self.dict[k] = v
        if m_previous is not None:
            for k, v in m_previous.groupdict().items():
                self.dict["bot"+k] = v


