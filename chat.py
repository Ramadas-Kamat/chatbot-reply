# Copyright (c) 2016 Gemini Lasswell
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Example use of chatbot_reply module, simple interactive mode """
from __future__ import print_function
from __future__ import unicode_literals

from chatbot_reply.six import text_type
from chatbot_reply.six.moves import input

from chatbot_reply import ChatbotEngine

if __name__ == "__main__":
    ch = ChatbotEngine(debug=False)
    ch.load_script_directory("scripts")
    print ("Type /quit to quit, /debug to toggle debug output, "
           "/botvars or /uservars to see values of variables, "
           "/reload to reload the scripts directory.")
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
        elif msg == "/debug":
            if ch._botvars["debug"] == "True":
                ch._botvars["debug"] = "False"
            else:
                ch._botvars["debug"] = "True"
        else:
            print("Bot> " + ch.reply("local", msg))
