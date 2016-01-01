#Any copyright is dedicated to the Public Domain.
#http://creativecommons.org/publicdomain/zero/1.0/

from chatbot_reply import Script, pattern

class ValveScript(Script):

    def __init__(self):
        self.alternates = {}
        self.alternates["mainvalve"] = "((shutoff|shut off|main|main water|city water) valve)"
        self.alternates["drainvalve"] = "([water] drain valve)"
        self.alternates["anyvalve"] = "({0}|{1})".format(self.alternates["mainvalve"],
                                                         self.alternates["drainvalve"])

    @pattern("status")
    def pattern_status(self):
        return ("Here is where I would tell you everything I know about "
                "the shutoff valve and the drain valve, as well as the water "
                "sensors.")

    @pattern("valve status")
    def pattern_valve_status(self):
        return "<shutoff valve status> <drain valve status> <water sensor status>"

    @pattern("_%a:mainvalve status")
    def pattern_what_is_the_mainvalve_status(self):
        return "The {{match0}} is {0}.".format(self.mainvalvestatus())

    @pattern("_%a:drainvalve status")
    def pattern_what_is_the_drainvalve_status(self):
        return "The {{match0}} is {0}.".format(self.drainvalvestatus())

    @pattern("(tell me about the|how is the|[what is] [the]) _%a:anyvalve status")
    def pattern_what_is_the_anyvalve_status(self):
        return "<{match0} status>"

    @pattern("is the _%a:anyvalve (open|closed)")
    def pattern_is_the_anyvalve_open_or_closed(self):
        return "<{match0} status>"

    @pattern("open [the] _%a:mainvalve")
    def pattern_open_the_mainvalve(self):
        if self.drainvalvestatus() == "open":
            return "The drain valve is open. Please close it before opening the {match0}."
        if self.leaksensorstatus() == "wet":
            return "<leak sensor status>. Please dry it and reset it before opening the {match0}."
        self.tellmainvalve("open")
        return "I'll tell the {match0} to open" + self.stall_for_time()

    @pattern("open [the] _%a:drainvalve")
    def pattern_open_the_drainvalve(self):
        if self.mainvalvestatus() == "open":
            return "The shutoff valve is open. Please close it first."
        else:
            self.telldrainvalve("open")
            return "I'll tell the {match0} to open" + self.stall_for_time()

    @pattern("close [the] _%a:mainvalve")
    def pattern_close_the_mainvalve(self):
        self.tellmainvalve("close")
        return "I'll tell the {match0} to close" + self.stall_for_time()

    @pattern("close [the] _%a:drainvalve")
    def pattern_close_the_drainvalve(self):
        self.telldrainvalve("close")
        return "I will tell the {match0} to close" + self.stall_for_time()

    def stall_for_time(self):
        return self.choose(" and get back to you shortly.",
                           ". Give me just a moment.",
                           ". I'll check back with you shortly."
                           ". I'll check back with you in a moment.",
                           " and get back to you in a moment.",
                           " and get back to you in just a moment.")

    @pattern("_(open|close) it", previous="* shutoff valve * drain valve *")
    def pattern_open_close_it_previous_both_valves(self):
        return "What do you want me to {match0}?"

    @pattern("_(open|close) it", previous="* _%a:anyvalve [*]")
    def pattern_open_close_it_previous_any_valve(self):
        return "<{match0} the {botmatch0}>"

    @pattern("_(open|close) [it]")
    def pattern_open_close_it(self):
        return "What do you want me to {match0}?"

    @pattern("[the] _%a:anyvalve", previous="what do you want me to (open|close)")
    def pattern_the_anyvalve_with_previous_whaddayawant(self):
        return "OK, <{botmatch0} the {match0}>"

    @pattern("[turn [the]] water on")
    def pattern_turn_the_water_on(self):
        if self.mainvalvestatus() == "open":
            return "It's already on."
        if self.leaksensorstatus() == "wet":
            return "<leak sensor status>. Please dry it and reset it before turning the water on."
        if self.drainvalvestatus() == "open":
            self.telldrainvalve("close")
            return "I closed the drain valve and <open shutoff valve>"
        else:
            return "<open shutoff valve>"

    @pattern("[turn [the]] water off")
    def pattern_turn_the_water_off(self):
        return "<close shutoff valve>"

    @pattern("drain [the] (water|house)")
    def pattern_drain_the_house(self):
        if self.drainvalvestatus() == "open":
            return "It's already drained."
        if self.mainvalvestatus() == "open":
            self.tellmainvalve("close")
            return "I closed the main valve and <open drain valve>"
        else:
            return "<open drain valve>"

    @pattern("(water|leak) sensor status")
    def pattern_water_sensor_status(self):
        return "The water leak sensor is {0]",format(self.leaksensorstatus())

    @pattern("setup test")
    def pattern_setup_test(self):
        Script.uservars["mainvalvestatus"] = "open"
        Script.uservars["drainvalvestatus"] = "closed"
        Script.uservars["leaksensorstatus"] = "dry"

    @pattern("sensor wet")
    def pattern_sensor_wet(self):
        Script.uservars["leaksensorstatus"] = "wet"        

    @pattern("sensor dry")
    def pattern_sensor_dry(self):
        Script.uservars["leaksensorstatus"] = "dry"

    def mainvalvestatus(self):
        return Script.uservars["mainvalvestatus"]

    def drainvalvestatus(self):
        return Script.uservars["drainvalvestatus"]        

    def tellmainvalve(self, todo):
        if todo == "close":
            newstate = "closed"
        else:
            newstate = "open"
        Script.uservars["mainvalvestatus"] = newstate

    def telldrainvalve(self, todo):
        if todo == "close":
            newstate = "closed"
        else:
            newstate = "open"
        Script.uservars["drainvalvestatus"] = newstate
        
    def leaksensorstatus(self):
        return Script.uservars["leaksensorstatus"]
