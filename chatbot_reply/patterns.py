#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Pattern Parsing for chatbot_reply
"""
from __future__ import print_function
from __future__ import unicode_literals
import re

from .exceptions import *

# TODO - could pass in a string such as "uba" with variable classes to create

class StopScanLoop(StopIteration):
    pass

class TokenMatcher(object):
    def __init__(self):
        self.regexes = []
        self.tokenizer = None
        self.token_classes = []
    def compile(self):
        self.tokenizer = re.compile("|".join(self.regexes), re.UNICODE)
    def add_definition(self, regex, token_class, lookahead):
        self.regexes.append(regex)
        self.token_classes.append(token_class)
        if lookahead:
            self.token_classes.append(None)
        

class PatternParser(object):
    """ Pattern Parser class for simplified regular expression patterns.
    """
    
    def __init__(self):
        """ Create a PatternParser object. All the internal work with regular
        expressions is done using unicode strings. If you pass in str's, a 
        TypeError will be raised. 
        """
        
        self._every_token = TokenMatcher()
        self._simple_tokens = TokenMatcher()

        token_definitions = [
            (False, (r"([*#@]\d*~?\d*)([])|\s]|$)", PatternParser.Wild, True)),
            (False, (r"(_)([*#@%([])", PatternParser.Memo, True)),
            (True,  (r"([^_\W][\w-]*)([])|\s]|$)", PatternParser.Word, True)),
            (True,  (r"([\s]+)", PatternParser.Space, False)),
            (False, (r"(%u:)([^_\d\W][\w]*)", PatternParser.Variable, True)),
            (False, (r"(%b:)([^_\d\W][\w]*)", PatternParser.Variable, True)),
            (False, (r"(%a:)([^_\d\W][\w]*)", PatternParser.Variable, True)),
            (True,  (r"(\[)", PatternParser.Optional, False)),
            (True,  (r"(\])([])|\s]|$)", PatternParser.Terminator, True)),
            (True,  (r"(\()", PatternParser.Group, False)),
            (True,  (r"(\))([])|\s]|$)", PatternParser.Terminator, True)),
            (True,  (r"(\|)", PatternParser.Pipe, False)),
            (True,  (r"(.)", PatternParser.Invalid, False))
            ]

        for simple_defn, defn in token_definitions:
            self._every_token.add_definition(*defn)
            if simple_defn:
                self._simple_tokens.add_definition(*defn)
                
        self._every_token.compile()
        self._simple_tokens.compile()

    ##### The public methods #####
    
    def parse(self, pattern, simple=False):
        if not isinstance(pattern, unicode):
            raise TypeError("Strings must be unicode.")
        if simple:
            token_matcher = self._simple_tokens
        else:
            token_matcher = self._every_token
        return self._parse(self._tokens(pattern, token_matcher))

    def score(self, pattern_tree):
        return sum(token.score(self) for token in pattern_tree)

    def format(self, pattern_tree):
        return "".join([token.format(self) for token in pattern_tree])

    def regex(self, pattern_tree, variables):
        def counter():
            i = 0
            while True:
                yield i
                i += 1
    
        result =  self._regex(pattern_tree, counter(), variables)
        return result
        
    ##### Parsing  #####
    
    def _parse(self, tokens, terminator=None, just_one=False):
        parsetree = []
        try:
            while True:
                token_class, text = next(tokens)
                token = token_class(self, tokens, text, terminator)
                token.add_to_parsetree(parsetree)
                if just_one:
                    break
        except StopScanLoop:
            pass
        except StopIteration:
            if terminator != None:
                raise PatternError("Missing a closing parenthesis "
                                   "or square bracket")
        PatternParser.Token._remove_trailing_space(parsetree)
        if not parsetree:
            raise PatternError("Pattern string is empty")
        return parsetree
            
    def _tokens(self, string, token_matcher):
        while True:
            m = token_matcher.tokenizer.match(string)
            if m is None:
                return
            index = m.lastindex
            token_class = token_matcher.token_classes[index - 1]
            if token_class is None:
                index = index - 1
            yield token_matcher.token_classes[index - 1], m.group(index)
            string = string[m.end(index):]
     

    ##### Regex generator  #####

    def _regex(self, pattern_tree, counter, variables):
        return "".join([token.regex(self, counter, variables)
                        for token in pattern_tree])

    # Subclass for the different types of token.
    # In Python, nested classes belong to the class they are nested in, not the
    # instance of the class, so they have no access to the "self" of the
    # enclosing object. But access to the enclosing class is necessary to
    # make recursive descent possible. There exist complicated solutions to make
    # bound subclasses, but today's simple solution is the "outerself" parameter
    # which needs to be explicitly passed by the enclosing object.

    class Token(object):
        @staticmethod
        def _group_tokens(results):
            tokens = [t for t in results if isinstance(t, PatternParser.Token)]
            if len(tokens) == 0:
                raise PatternError("Alternatives between parentheses or "
                                   "square brackets can't be empty")
            del results[-len(tokens):]
            results.append(tokens)

        @staticmethod
        def _remove_trailing_space(results):
            if (len(results) > 0 and
                isinstance(results[-1], PatternParser.Space)):
                results.pop()

    class Wild(Token):
        regexc = re.compile(r".(\d*)(~?)(\d*)", re.UNICODE)
        wildcards = {"@" : r"[^_\d\W]+",
                     "#" : r"\d+",
                     "*" : r"\w+"}
        def __init__(self, outerself, tokens, text, terminator):
            self.wild = text[0]
            self.minimum = "1"
            self.maximum = ""
                
            m = re.match(self.__class__.regexc, text)
            groups = m.groups()
            if groups[0]:
                self.minimum = self.maximum = groups[0]
            if groups[1]: #they gave us a ~
                self.maximum = groups[2]
            self.minimum = unicode(max(int(self.minimum), 1))
            if self.maximum:
                self.maximum = unicode(max(int(self.maximum),
                                           int(self.minimum)))

        def add_to_parsetree(self, parsetree):
            parsetree.append(self)

        def format(self, outerself):
            if self.minimum == self.maximum:
                return self.wild + self.minimum
            if int(self.minimum) == 1:
                if self.maximum == "":
                    return self.wild
                else:
                    return self.wild + "~" + self.maximum
            else:
                return self.wild + self.minimum + "~" + self.maximum

        def score(self, outerself):
            if self.wild == "*":
                return -2
            else:
                return -1

        def regex(self, outerself, counter, variables):
            wildcard = self.wildcards[self.wild]
            if self.maximum == "1":
                return wildcard + r"\b"
            else:
                # we are going to try to match n-1 repetitions of the pattern
                # followed by a space plus 1 rep of the pattern followed by a
                # \b
                min_str = unicode(int(self.minimum) - 1)
                max_str = self.maximum
                if max_str != "":
                    max_str = unicode(int(self.maximum) - 1)
                return (r"(" + wildcard + r"\s)" +
                        r"{" + min_str + r"," + max_str + r"}?"
                        + wildcard + r"\b")

    class Word(Token):
        def __init__(self, outerself, tokens, text, terminator):
            self.text = text
            
        def add_to_parsetree(self, parsetree):
            #if the last two things are a word and a space, merge them
            if (len(parsetree) > 1 and
                isinstance(parsetree[-1], PatternParser.Space) and
                isinstance(parsetree[-2], PatternParser.Word)):
                    parsetree[-2].text += (" " + self.text)
                    parsetree.pop()
            else:
                parsetree.append(self)

        def format(self, outerself):
            return self.text

        def score(self, outerself):
            return len(self.text.split(" ")) * 10

        def regex(self, outerself, counter, variables):
            return self.text + r"\b"

    class Memo(Token):
        def __init__(self, outerself, tokens, text, terminator):
            self.item = outerself._parse(tokens, just_one=True)[0]
                                         
        def add_to_parsetree(self, parsetree):
            parsetree.append(self)

        def format(self, outerself):
            return "_" + self.item.format(outerself)

        def score(self, outerself):
            return self.item.score(outerself)

        def regex(self, outerself, counter, variables):
            return "(?P<match{0}>{1})".format(counter.next(),
                self.item.regex(outerself, counter, variables))

    class Space(Token):
        def __init__(self, outerself, tokens, text, terminator):
            pass
        
        def add_to_parsetree(self, parsetree):
            # leading spaces (for example within a group) are ignored,
            # as are multiple spaces in a row
            if (len(parsetree) > 0 and isinstance(parsetree[-1], PatternParser.Token)
                and not isinstance(parsetree[-1], PatternParser.Space)):
                parsetree.append(self)
                
        def format(self, outerself):
            return " "

        def score(self, outerself):
            return 0

        def regex(self, outerself, counter, variables):
            return r"\s?"
        
    class Variable(Token):
        def __init__(self, outerself, tokens, text, terminator):
            self.var_id = text[1]
            self.var_name = outerself._parse(tokens, just_one=True)[0].text
            
        def add_to_parsetree(self, parsetree):
            parsetree.append(self)

        def format(self, outerself):
            return "%" + self.var_id + ":" + self.var_name

        def score(self, outerself):
            return 10

        def regex(self, outerself, counter, variables):
            if (self.var_id not in variables or
                self.var_name not in variables[self.var_id]):
                raise PatternVariableNotFoundError(
                    "Chatbot variable %{0}:{1} not found".format(self.var_id,
                                                                 self.var_name))
            value = variables[self.var_id][self.var_name]
            if not isinstance(value, unicode):
                raise PatternVariableValueError(
                    "Value in pattern variable %{0}:{1} could not be used "
                    "because it is not a unicode string.".format(
                        self.var_id, self.var_name))
            value = value.lower()
            try:
                parse_tree = outerself._parse(outerself._tokens(value,
                                              outerself._simple_tokens))
                regex = outerself.regex(parse_tree, None)
            except PatternError as e:
                e.args += (" in variable %{0}:{1}".format(self.var_id,
                                                          self.var_name),)
                raise

            return regex + r"\b"

    class Optional(Token):
        def __init__(self, outerself, tokens, text, terminator):
            self.choices = outerself._parse(tokens, "]")

        def add_to_parsetree(self, parsetree):
            parsetree.append(self)

        def format(self, outerself):
            output = [outerself.format(chunk) for chunk in self.choices]
            return "[" + "|".join(output) + "]"

        def score(self, outerself):
            return max([outerself.score(chunk) for chunk in self.choices])

        def regex(self, outerself, counter, variables):
            output = [outerself._regex(chunk, counter, variables)
                      for chunk in self.choices]
            return "(" + "|".join(output) + ")?"

    class Terminator(Token):
        def __init__(self, outerself, tokens, text, terminator):
            if terminator != text:
                raise PatternError("Found an unexpected {0}".format(text))

        def add_to_parsetree(self, parsetree):
            self._remove_trailing_space(parsetree)
            self._group_tokens(parsetree)
            raise StopScanLoop

    class Group(Token):
        def __init__(self, outerself, tokens, text, terminator):
            self.choices = outerself._parse(tokens, ")")

        def add_to_parsetree(self, parsetree):
            parsetree.append(self)

        def format(self, outerself):
            output = [outerself.format(chunk) for chunk in self.choices]
            return "(" + "|".join(output) + ")"

        def score(self, outerself):
            return max([outerself.score(chunk) for chunk in self.choices])

        def regex(self, outerself, counter, variables):
            output = [outerself._regex(chunk, counter, variables)
                      for chunk in self.choices]
            return "(" + "|".join(output) + ")"

    class Pipe(Token):
        def __init__(self, outerself, tokens, text, terminator):
            if terminator != ")" and terminator != "]":
                raise PatternError("Alternatives operator | must be "
                                   "used within parentheses or square "
                                   "brackets")
   
        def add_to_parsetree(self, parsetree):
            self._remove_trailing_space(parsetree)
            self._group_tokens(parsetree)

    class Invalid(Token):
        def __init__(self, outerself, tokens, text, terminator):
            raise PatternError("Found an unexpected character {0}".format(text))

 
class Pattern(object):
    pp = PatternParser()
    empty_score = pp.score(pp.parse("*"))
    def __init__(self, raw, alternates=None, simple=False, say=print):
        self.raw = raw
        self.alternates = alternates
        self._say = say
        if self.raw:
            self._parse_tree = self.pp.parse(raw, simple=simple)
            self.formatted_pattern = self.pp.format(self._parse_tree)
            self.score = self.pp.score(self._parse_tree)
            self.regexc = self._cache_regexc(alternates)
        else:
            self._parse_tree = None
            self.formatted_pattern = ""
            self.score = self.empty_score
            self.regexc = None

    def __len__(self):
        return len(self.raw)

    def _cache_regexc(self, alternates):
        try:
            regex = self.regex(alternates)
            self._say("Formatted Pattern: {0}, regex = {1}".format(
                self.formatted_pattern, regex))
            return re.compile(regex, flags=re.UNICODE)
        except PatternVariableNotFoundError:
            self._say("[Pattern] Failed to cache regex for {0}.".format(
                self.formatted_pattern))
            return None

    def regex(self, variables):
        return self.pp.regex(self._parse_tree, variables) + "$"

    def match(self, string, variables):
        if self.regexc:
            m = re.match(self.regexc, string)
        else:
            try:
                regex = self.regex(variables)
            except PatternVariableNotFoundError:
                return None
            m = re.match(regex, string, flags=re.UNICODE)
        return m
            
