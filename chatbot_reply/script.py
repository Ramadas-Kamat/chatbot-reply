#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" chatbot_reply.script, defines decorators and superclass for chatbot scripts 
"""
from __future__ import unicode_literals
from functools import wraps
import inspect
import random

from .exceptions import *
from .constants import _PREFIX

def rule(pattern_text, previous="", weight=1):
    def rule_decorator(func):
        @wraps(func)
        def func_wrapper(self, pattern=pattern_text, previous=previous,
                         weight=weight):
            result = func(self)
            try:
                return self.matches_format(self.choose(result))
            except Exception, e:
                name = (func.__module__[len(_PREFIX):] + "." +
                        self.__class__.__name__ + "." + func.__name__)
                msg = (" in @rule while processing return value "
                       "from {0}".format(name))
                e.args += (e.args[0] + msg,) + e.args[1:]
                raise
        return func_wrapper
    return rule_decorator

class ScriptRegistrar(type):
    registry = []
    def __new__(cls, name, bases, attributes):
        new_cls = type.__new__(cls, name, bases, attributes)
        if new_cls.__module__ != cls.__module__:
            cls.registry.append(new_cls)
        return new_cls

    @classmethod
    def clear(cls):
        cls.registry = []

class Script(object):
    __metaclass__ = ScriptRegistrar

    topic = "all"
    botvars = None
    uservars = None
    user = None
    match = None
    current_topic = None

    def setup(self):
        pass
    def setup_user(self, user):
        pass

    @classmethod
    def set_user(cls, user, uservars):
        cls.uservars = uservars
        cls.user = user
        cls.current_topic = uservars["__topic__"]
    
    @classmethod
    def set_topic(cls, new_topic):
        cls.current_topic = new_topic
        pass
    
    def choose(self, args):
        # self.choose can be a flexible thing, variable number of arguments
        # and they can be either strings or (string, weight) tuples
        # or just return either a string or a list to be fed to self.choose
        if args is None or not args:
            reply = ""
        else:
            reply = args
        if isinstance(args, list) and args:
            reply = random.choice(args)
            if isinstance(args[0], tuple):
                args = [(string, max(1, weight)) for string, weight in args]
                total = sum([weight for string, weight in args])
                choice = random.randrange(total)
                for string, weight in args:
                    if choice < abs(weight):
                        reply = string
                        break
                    else:
                        choice -= abs(weight)
        return reply

    def matches_format(self, string):
        return string.format(*[], **Script.match)
    

