#Any copyright is dedicated to the Public Domain.
#http://creativecommons.org/publicdomain/zero/1.0/

from chatbot_reply import Script, pattern

class HokeyPokeyScript(Script):
    def __init__(self):
        Script.botvars["mood"] = "good"
        Script.botvars["bodypart"] = "right foot"
        Script.botvars["danced"] = False
        self.bodyparts = ['right foot', 'left foot', 'right arm',
                                       'left arm', 'whole self']

    @pattern("how are you doing")
    def pattern_how_are_you_doing(self):
        mood = Script.botvars["mood"]
        return "I'm in a {0} mood.".format(mood)

    @pattern("get grumpy")
    def pattern_get_grumpy(self):
        Script.botvars["mood"] = "bad"
        return "Now I'm grouchy."

    @pattern("get happy")
    def pattern_get_happy(self):
        Script.botvars["mood"] = "good"
        return "I feel much better."

    @pattern("hey [there]")
    def pattern_hey_opt(self):
        if Script.botvars["mood"] == "good":
            return "<hello>"
        else:
            return "Hay is for horses."

    @pattern("hello _*")
    def pattern_hello_star(self):
        return "<hello> {0}".format(Script.match[0])

    @pattern("knock knock")
    def pattern_knock_knock(self):
        return "Who's there?"

    @pattern("_*", previous="who is there")
    def pattern_star_prev_who_is_there(self):
        return "{0} who?".format(Script.match[0])

    @pattern("_*", previous="* who")
    def pattern_star_prev_star_who(self):
        return "Lol %s! That's a good one!".format(Script.match[0])

    @pattern("put your _* in")
    def pattern_put_your_star_in(self):
        return ("I put my {0} in, I put my {0} out, "
                "I shake it all about!".format(Script.match[0]))

    @pattern("where are you in the dance")
    def pattern_where_are_you_in_the_dance(self):
        return "I'm about to use my {0}.".format(Script.botvars["bodypart"])

    @pattern("back to the right foot")
    def pattern_back_to_the_right_foot(self):
        Script.botvars["bodypart"] = "right foot"
        return ["OK, I'm back on the right foot."]

    @pattern("what would the next one be")
    def pattern_what_would_the_next_one_be(self):
        next_part = self.next_body_part(Script.botvars["bodypart"])
        return "After {0} comes {1}.".format((Script.botvars["bodypart"],
                                            next_part))

    @pattern("skip to the next one")
    def pattern_skip_to_the_next_one(self):
        Script.botvars["bodypart"] = self.next_body_part(Script.botvars["bodypart"])
        return "OK, when I dance I'll use my {0}.".format(Script.botvars["bodypart"])

    @pattern("do the hokey pokey")
    def pattern_do_the_hokey_pokey(self):
        Script.botvars["danced"] = True
        bodypart = Script.botvars["bodypart"]
        Script.botvars["bodypart"] = self.next_body_part(bodypart)
        return "<put your {0} in>".format(bodypart)
    
    @pattern("(have you done|did you do) the hokey pokey")
    def pattern_have_you_done_the_hokey_pokey(self):
        if Script.botvars["danced"]:
            return "Yes!"
        else:
            return "No, but I'd like to!"

    def next_body_part(self, bodypart):
        return self.bodyparts[(self.bodyparts.index(bodypart) + 1)
                              % len(self.bodyparts)]
    
