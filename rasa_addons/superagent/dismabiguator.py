import json
import re
from schema import Schema, And, Optional
from rasa_core.actions.action import Action
from rasa_core.events import Restarted


class Disambiguator(object):
    def __init__(self, rules):
        rules = rules["nlu"] if "nlu" in rules else {}

        self.schema = Schema({Optional("disambiguation"): {
                                "trigger": And(str, len),
                                Optional("max_suggestions", default=2): int,
                                "display": {
                                    Optional("intro_template"): And(str, len),
                                    "text_template": And(str, len, error="text_template is required"),
                                    Optional("button_title_template_prefix", default="utter_disamb"): And(str, len),
                                    Optional("fallback_button"): {
                                        "title": And(str, len, error="fallback button title is required"),
                                        "payload": And(str, len, error="fallback button payload is required")
                                    }
                                }   
                            },
                            Optional("fallback"): {
                                "trigger": And(str, len),
                                "display": {
                                    "text": And(str, len),
                                    Optional("buttons"): 
                                        [{"title": And(str, len, error="button title is required"), 
                                        "payload": And(str, len, error="button title is required")}]
                                    }
                                }
                            })

        self.schema.validate(rules)

        self.disamb_rule = rules.get("disambiguation", None)
        self.fallback_rule = rules.get("fallback", None)

        if self.disamb_rule and "max_suggestion" not in self.disamb_rule:
            self.disamb_rule["max_suggestions"] = 2

        if self.disamb_rule and "button_title_template_prefix" not in self.disamb_rule["display"]:
            self.disamb_rule["display"]["button_title_template_prefix"] = "utter_disamb"

    @staticmethod
    def is_triggered(parse_data, trigger):
        pattern = re.compile(r"\$(\d)")
        eval_string = trigger
        matches = re.findall(pattern, trigger)
        for i in matches:
            # if not enough intents in ranking to apply the rule, no fallback can be done
            if int(i) >= len(parse_data["intent_ranking"]):
                return False
            eval_string = re.sub(r'\$' + i, str(parse_data["intent_ranking"][int(i)]["confidence"]), eval_string)

        return len(parse_data["intent_ranking"]) and eval(eval_string, {'__builtins__': {}})

    def should_fallback(self, parse_data):
        if not self.fallback_rule or "intent_ranking" not in parse_data:
            return False

        return self.is_triggered(parse_data, self.fallback_rule["trigger"])

    def should_disambiguate(self, parse_data):
        if not self.disamb_rule or "intent_ranking" not in parse_data:
            return False

        return self.is_triggered(parse_data, self.disamb_rule["trigger"])

    def get_payloads(self, parse_data, keep_entities=True):
        intents = list(map(lambda x: x["name"], parse_data["intent_ranking"]))[:self.disamb_rule["max_suggestions"]]
        entities = ""
        if "entities" in parse_data and keep_entities:
            entities = json.dumps(dict(map(lambda e: (e["entity"], e["value"]), parse_data["entities"])))
        payloads = list(["/{}{}".format(i, entities) for i in intents])
        return payloads

    def get_intent_names(self, parse_data):
        return list(map(lambda x: x["name"], parse_data["intent_ranking"]))[:self.disamb_rule["max_suggestions"]]

    def disambiguate(self, parse_data, tracker, dispatcher, run_action):
        should_disambiguate = self.should_disambiguate(parse_data)

        if should_disambiguate:
            action = ActionDisambiguate(self.disamb_rule, self.get_payloads(parse_data), self.get_intent_names(parse_data))
            run_action(action, tracker, dispatcher)
            return True

    def fallback(self, parse_data, tracker, dispatcher, run_action):
        should_fallback = self.should_fallback(parse_data)

        if should_fallback:
            action = ActionFallback(self.fallback_rule)
            run_action(action, tracker, dispatcher)
            return True

class ActionDisambiguate(Action):

    def __init__(self, rule, payloads, intents):
        self.rule = rule
        self.payloads = payloads
        self.intents = intents

    @staticmethod
    def get_disambiguation_message(dispatcher, rule, payloads, intents):
        buttons = list(
            [{"title": dispatcher.retrieve_template(
                "{}_{}".format(rule["display"]["button_title_template_prefix"], i[0]))[
                "text"], "payload": i[1]} for i in zip(intents, payloads)])

        if "fallback_button" in rule["display"] and \
            "title" in rule["display"]["fallback_button"] and \
            "payload" in rule["display"]["fallback_button"]:
            buttons.append(
                {"title": dispatcher.retrieve_template(rule["display"]["fallback_button"]["title"])["text"],
                 "payload": rule["display"]["fallback_button"]["payload"]
                 })

        disambiguation_message = {
            "text": dispatcher.retrieve_template(rule["display"]["text_template"])["text"],
            "buttons": buttons
        }

        return disambiguation_message

    def run(self, dispatcher, tracker, domain):
        if "intro_template" in self.rule["display"]:
            dispatcher.utter_template(self.rule["display"]["intro_template"])

        disambiguation_message = self.get_disambiguation_message(dispatcher, self.rule, self.payloads, self.intents)

        dispatcher.utter_response(disambiguation_message)
        return [Restarted()]

    def name(self):
        return 'action_disambiguate'

class ActionFallback(Action):

    def __init__(self, rule):
        self.rule = rule

    @staticmethod
    def get_fallback_message(dispatcher, rule):
        fallback_message = {
            "text": dispatcher.retrieve_template(rule["display"]["text"])["text"]
        }
        if "buttons" in rule["display"]:
            buttons = list(
                [{"title": dispatcher.retrieve_template(button["title"])["text"], 
                "payload": button["payload"]} for button in rule["display"]["buttons"]])
            fallback_message["buttons"] = buttons
        return fallback_message

    def run(self, dispatcher, tracker, domain):

        fallback_message = self.get_fallback_message(dispatcher, self.rule)

        dispatcher.utter_response(fallback_message)
        return [Restarted()]

    def name(self):
        return 'action_fallback'