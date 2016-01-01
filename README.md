# chatbot_reply
Chatbot Reply Generator in Python

##about this project
My goal is to create a scriptable chatbot engine for Python that could be easily integrated into larger projects. By chatbot engine, I mean software that produces responses to user messages, either text responses or the execution of Python code or both, but that isn't responsible for receiving or delivering them.

##project goals
- No event handling or message delivery, so that it's easy to integrate into systems that already have both of those.
- Rules for matching input and responses expressed in readable Python code.
- Ability to import rules from a directory of Python files, so the rules can be external to the software package.
- Ability to run arbitrary Python code when a rule matches.
- Match user input against simplified regular expressions.
- No built in natural language processing, but nothing stopping a rules module from importing nltk and taking full advantage of it.

##current status
It's a work in progress. Check back soon for something that might be useful.
