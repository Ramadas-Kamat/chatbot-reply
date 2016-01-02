#Any copyright is dedicated to the Public Domain.
#http://creativecommons.org/publicdomain/zero/1.0/

from chatbot_reply import Script, pattern

class TutorialScript(Script):
    def __init__(self):
        self.alternates = {"colors": "(red|yellow|orange|green|blue|violet)"}
        
    @pattern("hello robot")
    def pattern_hello_robot(self):
        return "Hello, carbon-based life form!"
        
    @pattern("how are you", weight=2)
    def pattern_how_are_you(self):
        return ["I'm great, how are you?",
                "Doing awesome, you?",
                "Great! You?",
                "I'm fine, thanks for asking!"]

    @pattern("say something random")
    def pattern_say_something_random(self):
        word = self.choose(["it's fun", "potato"])
        return "I like being random because {0}.".format(word)

    @pattern("greetings")
    def pattern_greetings(self):
        return [("Hello!", 20),
                ("Buenas dias!", 25),
                ("Buongiorno!", 1)]

    @pattern("_* told me to say _*")
    def pattern_star2_told_me_to_say_star(self):
        return ['Why would {match0} tell you to say "{match1}"?',
                'Are you just saying "{match1}" because {match0} told you to?']
    
    @pattern("i am _#1 years old")
    def pattern_i_am_number1_years_old(self):
        return "{match0} isn't old at all!"

    @pattern("who is _*")
    def pattern_who_is_star(self):
        return "I don't know who {match0} is."

    @pattern("*")
    def pattern_star(self):
        return ["I don't know how to reply to that.",
                "Can you rephrase that?",
                "Let's change the subject."]

    @pattern("i am @~3 years old")
    def pattern_i_am_atsign3_years_old(self):
        return "Tell me that again, but with a number this time."

    @pattern("i am * years old")
    def pattern_i_am_star_years_old(self):
        return "Can you use a number instead?"

    @pattern("are you a (bot|robot|computer|machine)")
    def pattern_are_you_a_alt(self):
        return "Darn! You got me!"

    @pattern("i am _(so|really|very) excited")
    def pattern_i_am_alt_excited(self):
        return "What are you {match0} excited about?"

    @pattern("i _(like|love) the color _*")
    def pattern_i_alt_the_color_star(self):
        return ["What a coincidence! I {match0} that color too!",
                "The color {match1} is one of my favorites"
                "Really? I {match0} the color {1} too!"
                "Oh I {match0} {match1} too!"]

    @pattern("how [are] you")
    def pattern_how_opt_you(self):
        return "I'm great, you?"

    @pattern("what is your (home|office|cell) [phone] number")
    def pattern_what_is_your_alt_opt_number(self):
        return "You can reach me at: 1 (800) 555-1234."

    @pattern("I have a [red|green|blue] car")
    def pattern_i_have_a_optalt_car(self):
        return "I bet you like your car a lot."

    @pattern("[*] the matrix [*]")
    def pattern_optstar_the_matrix_optstar(self):
        return "How do you know about the matrix?"

    @pattern("what color is my _(red|blue|green|yellow) _*")
    def pattern_what_color_is_my_alt_star(self):
        return "According to you, your {match1} is {match0}."

    @pattern("my * is _%a:colors")
    def pattern_my_star_is_arrcolors(self):
        return "I've always wanted a {match1} {match0}"

    @pattern("google _*", weight=10)
    def pattern_google_star(self):
        return "OK, I'll google it. Jk, I'm not Siri."

    @pattern("_* or whatever", weight=100)
    def pattern_star_or_whatever(self):
        return "Whatever. <{match0}>"

    @pattern("hello")
    def pattern_hello(self):
        return ["Hi there!", "Hey!", "Howdy!"]

    @pattern("hi")
    def pattern_hi(self):
        return "<hello>"

    @pattern("my name is _*~3")
    def pattern_my_name_is_star(self):
        Script.uservars["name"] = Script.match[0] # some equivalent of formal, or maybe raw input
        return "It's nice to meet you, {match0}."

    @pattern("what is my name")
    def pattern_what_is_my_name(self):
        if "name" not in Script.uservars:
            return "You never told me your name."
        else:
            return ["Your name is {0}.".format(Script.uservars["name"]),
                    "You told me your name is {0}.".format(Script.uservars["name"])]

    
