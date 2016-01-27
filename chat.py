# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Example use of chatbot_reply module, simple interactive mode """
from __future__ import print_function
from __future__ import unicode_literals
import logging

from chatbot_reply.six import text_type
from chatbot_reply.six.moves import input

from chatbot_reply import ChatbotEngine

if __name__ == "__main__":
    log = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.ERROR)

    ch = ChatbotEngine()
    ch.load_script_directory("scripts")
    print ("Type /quit to quit, "
           "/botvars or /uservars to see values of variables, "
           "/reload to reload the scripts directory,"
           "/log plus debug, info, warning or error to set logging level.")
    while True:
        msg = text_type(input("You> "))
        if msg == "/quit":
            break
        elif msg == "/botvars":
            print(text_type(ch._botvars))
        elif msg == "/uservars":
            if "local" in ch._users:
                print(text_type(ch._users["local"].vars))
            else:
                print("No user variables have been defined.")
        elif msg == "/reload":
            ch.clear_rules()
            ch.load_script_directory("scripts")
        elif msg == "/log debug":
            log.setLevel(logging.DEBUG)
        elif msg == "/log info":
            log.setLevel(logging.INFO)
        elif msg == "/log warning":
            log.setLevel(logging.WARNING)
        elif msg == "/log error":
            log.setLevel(logging.ERROR)
        else:
            print("Bot> " + ch.reply("local", {}, msg))
