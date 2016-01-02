#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Pattern Parsing for chatbot_reply
"""
import re

from .exceptions import *

# TODO - could pass in a string such as "uba" with variable classes to create
# TODO - replace all those tuples in the parse tree with class instances
# TODO - add a wrapper for re.match that gets the unicode right
# TODO - make the exception classes handle unicode to str conversion
# TODO - unicode literals wouuld probably work here

class StopScanLoop(StopIteration):
    pass

class PatternParser(object):
    """ Pattern Parser class for simplified regular expression patterns.
        public instance variable : encoding
    """
    

    def __init__(self):
        """ Create a PatternParser object. All the internal work with regular
        expressions is done using unicode strings. If you pass in str's, they
        will be converted to unicode using the encoding keyword parameter,
        which defaults to utf-8.

        That being said, the output of PatternParser.regex isn't going to work
        on str's containing special characters unless you convert them to unicode
        and use re.UNICODE.
        """
        self.encoding = "utf-8"
        
        self._every_token = TokenMatcher()
        self._alternates_tokens = TokenMatcher()
        self._variables_tokens = TokenMatcher()

        EVA = [self._every_token, self._alternates_tokens,
               self._variables_tokens]
        EV = [self._every_token, self._variables_tokens]
        E =  [self._every_token]

        self._matcher_group = TokenMatcherGroup()
        for m in EVA:
            self._matcher_group.add_matcher(m)

        token_definitions = [
            (r"([*#@]\d*~?\d*)([])|\s]|$)", E, PatternParser.Wild(), True),
            (r"(_)([*#@%([])", E, PatternParser.Memo(), True),
            (r"([^_\W][\w-]*)([])|\s]|$)", EVA, PatternParser.Word(), True),
            (r"([\s]+)", EVA, PatternParser.Space(), False),
            (r"(%u:)([^_\d\W][\w]*)", E, PatternParser.Variable(), True),
            (r"(%b:)([^_\d\W][\w]*)", E, PatternParser.Variable(), True),
            (r"(%a:)([^_\d\W][\w]*)", E, PatternParser.Variable(), True),
            (r"(\[)", EVA, PatternParser.Optional(), False),
            (r"(\])([])|\s]|$)", EVA, PatternParser.Terminator(), True),
            (r"(\()", EVA, PatternParser.Group(), False),
            (r"(\))([])|\s]|$)", EVA, PatternParser.Terminator(), True),
            (r"(\|)", EVA, PatternParser.Pipe(), False),
            (r"(.)", EVA, PatternParser.Invalid(), False)
            ]

        for d in token_definitions:
            self._matcher_group.add_token(*d)

        self._matcher_group.compile_all()


    ##### The public methods #####
    
    def parse(self, pattern, simple=False):
        if isinstance(pattern, str):
            pattern = unicode(pattern, self.encoding)
        if simple:
            tokenizer = self._alternates_tokens.tokenizer
        else:
            tokenizer = self._every_token.tokenizer
        return self._parse(self._tokens(pattern, tokenizer))

    def score(self, pattern_tree):
        return sum(self._score_tuple(tup) for tup in pattern_tree)

    def format(self, pattern_tree):
        output = [self._format_pattern_tuple(tup) for tup in pattern_tree]
        result = "".join(output)
        if isinstance(result, unicode):
            result = result.decode(self.encoding)
        return result

    # need to wrap this in something that handles unicode correctly
    def regex(self, pattern_tree, variables):
        named_groups = [0]
        result =  self._regex(pattern_tree, named_groups, variables)
        if isinstance(result, str):
            result = unicode(result, self.encoding)
        return result
        
    ##### Parsing  #####
    
    def _parse(self, tokens, terminator=None, just_one=False):
        parsetree = []
        try:
            while True:
                code, text = next(tokens)
                self._matcher_group.tools(code).parse(self, tokens, parsetree,
                                                    code, text, terminator)
                if just_one:
                    break
        except StopScanLoop:
            pass
        except StopIteration:
            if terminator != None:
                raise PatternError("Missing a closing parenthesis "
                                   "or square bracket")
        self._remove_trailing_space(parsetree)
        if not parsetree:
            raise PatternError("Pattern string is empty")
        return parsetree
            
    def _tokens(self, string, tokenizer):
        while True:
            m = tokenizer.match(string)
            if m is None:
                return
            index = m.lastindex
            tools = self._matcher_group.tools(index - 1)
            if tools is None:
                index = index - 1
            yield index - 1, m.group(index)
            string = string[m.end(index):]
     
    def _group_tuples(self, results):
        tups = [t for t in results if isinstance(t, tuple)]
        if len(tups) == 0:
            raise PatternError("Alternatives between parentheses or "
                               "square brackets can't be empty")
        del results[-len(tups):]
        results.append(tups)

    def _remove_trailing_space(self, results):
        if (len(results) > 0 and self._token_name(results[-1]) == "space"):
            results.pop()

    def _token_name(self, parsetree_element):
        if isinstance(parsetree_element, list):
            return None
        else:
            return self._matcher_group.token_name(parsetree_element[0])
        
    ##### Formatting  #####

    def _format_pattern_tuple(self, tup):
        return self._matcher_group.tools(tup[0]).format(self, tup[0], tup[1])

    ##### complexity scoring #####

    def _score_tuple(self, tup):
        return self._matcher_group.tools(tup[0]).score(self, tup[0], tup[1])
    
    ##### Regex generator  #####

    def _regex(self, pattern_tree, named_groups, variables):
        output = [self._regex_pattern_tuple(tup, named_groups, variables)
                  for tup in pattern_tree]
        return "".join(output)

    def _regex_pattern_tuple(self, tup, named_groups, variables):
        return self._matcher_group.tools(tup[0]).regex(self, tup[0], tup[1],
                                                      named_groups, variables)

    # Subclass for the different types of token.
    # In Python, nested classes belong to the class they are nested in, not the
    # instance of the class, so they have no access to the "self" of the
    # enclosing object. But access to the enclosing class is necessary to
    # make recursive descent possible. There exist complicated solutions to make
    # bound subclasses, but today's simple solution is the "outerself" parameter
    # which needs to be explicitly passed by the enclosing object.

    class Token(object):
        def __init__(self):
            self.name = self.__class__.__name__.lower()
        pass

    class Wild(Token):
        regexc = re.compile(r".(\d*)(~?)(\d*)", re.UNICODE)
        wildcards = {"@" : r"[^_\d\W]+",
                     "#" : r"\d+",
                     "*" : r"\w+"}

        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            wildcard_type = text[0]
            minimum = "1"
            maximum = ""
                
            m = re.match(self.__class__.regexc, text)
            groups = m.groups()
            if groups[0]:
                minimum = maximum = groups[0]
            if groups[1]: #they gave us a ~
                maximum = groups[2]
            minimum = str(max(int(minimum), 1))
            if maximum:
                maximum = str(max(int(maximum), int(minimum)))
            parsetree.append((code, (wildcard_type, minimum, maximum)))

        def format(self, outerself, code, data):
            minimum, maximum = data[1], data[2]
            wild = data[0]
            if minimum == maximum:
                return wild + minimum
            if int(minimum) == 1:
                if maximum == "":
                    return wild
                else:
                    return wild + "~" + maximum
            else:
                return wild + minimum + "~" + maximum

        def score(self, outerself, code, data):
            if data[0] == "*":
                return -2
            else:
                return -1

        def regex(self, outerself, code, data, named_groups, variables):
            minimum, maximum = data[1], data[2]
            wildcard = self.__class__.wildcards[data[0]]
            if maximum == "1":
                return wildcard + r"\b"
            else:
                # we are going to try to match n-1 repetitions of the pattern
                # followed by a space plus 1 rep of the pattern followed by a
                # \b
                minimum = str(int(minimum) - 1)
                if maximum != "":
                    maximum = str(int(maximum) - 1)
                return (r"(" + wildcard + r"\s)" +
                        r"{" + minimum + r"," + maximum + r"}?"
                        + wildcard + r"\b")

    class Word(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            #if the last two things are a word and a space, merge them
            if (len(parsetree) > 1 and
                outerself._token_name(parsetree[-1]) == "space" and
                outerself._token_name(parsetree[-2]) == "word"):
                    parsetree[-2] = (code, parsetree[-2][1] + " " + text)
                    parsetree.pop()
            else:
                parsetree.append((code, text))

        def format(self, outerself, code, data):
            return data

        def score(self, outerself, code, data):
            return len(data.split(" ")) * 10

        def regex(self, outerself, code, data, named_groups, variables):
            return data + r"\b"

    class Memo(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            item = outerself._parse(tokens, just_one=True)
            parsetree.append((code, item[0]))

        def format(self, outerself, code, data):
            return "_" + outerself._format_pattern_tuple(data)

        def score(self, outerself, code, data):
            return outerself._score_tuple(data)

        def regex(self, outerself, code, data, named_groups, variables):
            regex = u"(?P<match{0}>{1})".format(
                named_groups[0],
                outerself._regex_pattern_tuple(data, named_groups, variables))
            named_groups[0] += 1
            return regex

    class Space(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            # leading spaces (for example within a group) are ignored,
            # as are multiple spaces in a row
            if (len(parsetree) > 0 and isinstance(parsetree[-1], tuple)
                and outerself._token_name(parsetree[-1]) != "space"):
                parsetree.append((code, text))
                
        def format(self, outerself, code, data):
            return data

        def score(self, outerself, code, data):
            return 0

        def regex(self, outerself, code, data, named_groups, variables):
            return r"\s?"
        
    class Variable(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            name = outerself._parse(tokens, just_one=True)
            parsetree.append((code, (text[1], name[0][1])))

        def format(self, outerself, code, data):
            return "%" + data[0] + ":" + data[1]

        def score(self, outerself, code, data):
            return 10

        def regex(self, outerself, code, data, named_groups, variables):
            if data[0] not in variables or data[1] not in variables[data[0]]:
                raise PatternVariableNotFoundError(
                    u"Chatbot variable %{0}:{1} not found".format(data[0],
                                                                 data[1]))
            value = variables[data[0]][data[1]]
            if isinstance(value, str):
                value = unicode(value, outerself.encoding)
            if not isinstance(value, unicode):
                raise PatternVariableValueError(
                    u"Value in pattern variable %{0}:{1} "
                    "could not be used because it is not a string.".format(
                        data[0], data[1]))
            value = value.lower()
            try:
                parse_tree = outerself._parse(
                    outerself._tokens(value,
                                      outerself._variables_tokens.tokenizer))
                regex = outerself.regex(parse_tree, None)
            except PatternError as e:
                e.args += (u" in variable %{0}:{1}".format(data[0], data[1]),)
                raise

            return regex + r"\b"

    class Optional(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            parsetree.append((code, outerself._parse(tokens, "]")))

        def format(self, outerself, code, data):
            output = [outerself.format(chunk) for chunk in data]
            return "[" + "|".join(output) + "]"

        def score(self, outerself, code, data):
            return max([outerself.score(chunk) for chunk in data])

        def regex(self, outerself, code, data, named_groups, variables):
            output = [outerself._regex(chunk, named_groups, variables)
                      for chunk in data]
            return "(" + "|".join(output) + ")?"

    class Terminator(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            if terminator != text:
                raise PatternError("Found an unexpected {0}".format(text))
            outerself._remove_trailing_space(parsetree)
            outerself._group_tuples(parsetree)
            raise StopScanLoop

    class Group(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            parsetree.append((code, outerself._parse(tokens, ")")))

        def format(self, outerself, code, data):
            output = [outerself.format(chunk) for chunk in data]
            return "(" + "|".join(output) + ")"

        def score(self, outerself, code, data):
            return max([outerself.score(chunk) for chunk in data])

        def regex(self, outerself, code, data, named_groups, variables):
            output = [outerself._regex(chunk, named_groups, variables)
                      for chunk in data]
            return "(" + "|".join(output) + ")"

    class Pipe(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            if terminator != ")" and terminator != "]":
                raise PatternError("Alternatives operator | must be "
                                   "used within parentheses or square "
                                   "brackets")
            outerself._remove_trailing_space(parsetree)
            outerself._group_tuples(parsetree)

    class Invalid(Token):
        def parse(self, outerself, tokens, parsetree, code, text, terminator):
            raise PatternError(u"Found an unexpected character {0}".format(text))

 
class TokenMatcher(object):
    def __init__(self):
        self.regexes = []
        self.tokenizer = None
    def compile(self):
        self.tokenizer = re.compile("|".join(self.regexes), re.UNICODE)

class TokenMatcherGroup(object):
    def __init__(self):
        self.tokennames = []
        self.tokentools = []
        self.all_matchers = []

    def add_matcher(self, matcher):
        self.all_matchers.append(matcher)

    def token_name(self, code):
        return self.tokennames[code]

    def tools(self, code):
        return self.tokentools[code]

    def add_token(self, regex, matchers, tokentools, lookahead):
        self.tokennames.append(tokentools.name)
        for m in self.all_matchers:
            if m not in matchers:
                # if this matcher isn't supposed to match this token type,
                # replace the regex with one that will never match anything.
                regex = r"([^\W\w])"
                if lookahead:
                    regex += r"([^\W\w])"
            m.regexes.append(regex)

        self.tokentools.append(tokentools)
        if lookahead:
            self.tokennames.append(None)
            self.tokentools.append(None)

    def compile_all(self):
        for m in self.all_matchers:
            m.compile()
