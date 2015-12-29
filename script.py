#! /usr/bin/env python
# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" pycharge.script module, defines decorators and superclass for 
pycharge scripts 

"""
#todo - Script needs a method that does string.format using the match variables
from functools import wraps
import random

def pattern(pattern_text, previous="", weight=1):
    def pattern_decorator(func):
        @wraps(func)
        def func_wrapper(self, pattern=pattern_text, previous=previous,
                         weight=weight):
            return self.choose(func(self))
        return func_wrapper
    return pattern_decorator

def alternates(array_name):
    def alternates_decorator(func):
        @wraps(func)
        def func_wrapper(self, name=array_name):
            return func(self)
        return func_wrapper
    return alternates_decorator

def substitutions(subs, person=False):
    def substitutions_decorator(func):
        @wraps(func)
        def func_wrapper(self, name=subs, person=person):
            return func(self)
        return func_wrapper
    return substitutions_decorator

class Script(object):
    topic = "all"
    
    botvars = None
    uservars = None
    user_id = None
    match = None
    current_topic = None

    @classmethod
    def set_user(cls, user, uservars):
        cls.uservars = uservars
        cls.user_id = user
        cls.current_topic = uservars["__topic__"]
    
    @classmethod
    def set_topic(cls, new_topic):
        cls.current_topic = new_topic
        pass
    
    def setUp(self):
        pass

    @staticmethod
    def choose(args):
        # self.choose can be a flexible thing, variable number of arguments
        # and they can be either strings or (string, weight) tuples
        # or just return either a string or a list to be fed to self.choose
        reply = args
        if isinstance(args, list) and args:
            reply = random.choice(args)
            if isinstance(args[0], tuple):
                args = [(string, min(1, weight)) for string, weight in args]
                total = sum([weight for string, weight in args])
                choice = random.randrange(total)
                for string, weight in args:
                    if choice < abs(weight):
                        reply = string
                        break
                    else:
                        choice -= abs(weight)
        return reply
    
