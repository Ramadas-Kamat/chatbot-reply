# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Exceptions for chatbot_reply
"""
class PatternError(Exception):
    pass
class PatternVariableNotFoundError(Exception):
    pass
class NoRulesFoundError(Exception):
    pass
class PatternMethodSpecError(Exception):
    pass
class RecursionTooDeepError(Exception):
    pass

