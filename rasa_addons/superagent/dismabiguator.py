import json
import re
from schema import Schema, And, Optional
from rasa_core.actions.action import Action
from rasa_core.events import Restarted


class Disambiguator(object):
    def __init__(self, rule):
        self.rule = rule["nlu"] if "nlu" in rule else {}

        self.schema = Schema({"trigger": And(str, len),
                              "display": {
                                  'type': And(str, lambda t: t in ["text_with_buttons"], error="type must be text_with_buttons"),
                                  Optional("intro_template"):  And(str, len),
                                  "text_template":  And(str, len, error="text_template is required"),
                                  Optional("button_title_template_prefix", default="utter_disamb"): And(str, len),
                                  Optional("fallback_title"): And(str, len, error="fallback_title is required"),
                                  Optional("fallback_payload"): And(str, len, error="fallback_payload is required"),
                                  Optional("max_suggestions", default=2): int}
                              })

        self.schema.validate(self.rule)

        if "max_suggestion" not in self.rule["display"]:
            self.rule["display"]["max_suggestions"] = 2

        if "button_title_template_prefix" not in self.rule["display"]:
            self.rule["display"]["button_title_template_prefix"] = "utter_disamb"

    def should_disambiguate(self, parse_data):
        if "intent_ranking" not in parse_data:
            return False

        pattern = re.compile(r"\$(\d)")
        eval_string = self.rule["trigger"]
        matches = re.findall(pattern, self.rule["trigger"])
        for i in matches:
            # if not enough intents in ranking to apply the rule, no disambiguation can be done
            if int(i) >= len(parse_data["intent_ranking"]):
                return False
            eval_string = re.sub(r'\$' + i, str(parse_data["intent_ranking"][int(i)]["confidence"]), eval_string)

        return len(parse_data["intent_ranking"]) and eval(eval_string, {'__builtins__': {}})

    def get_payloads(self, parse_data, keep_entities=True):
        intents = list(map(lambda x: x["name"], parse_data["intent_ranking"]))[:self.rule["display"]["max_suggestions"]]
        entities = ""
        if "entities" in parse_data and keep_entities:
            entities = json.dumps(dict(map(lambda e: (e["entity"], e["value"]), parse_data["entities"])))
        payloads = list(["/{}{}".format(i, entities) for i in intents])
        return payloads

    def get_intent_names(self, parse_data):
        return list(map(lambda x: x["name"], parse_data["intent_ranking"]))[:self.rule["display"]["max_suggestions"]]

    def disambiguate(self, parse_data, tracker, dispatcher, run_action):
        should_disambiguate = self.should_disambiguate(parse_data)

        if should_disambiguate:
            action = ActionDisambiguate(self.rule, self.get_payloads(parse_data), self.get_intent_names(parse_data))
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

        if "fallback_title" in rule["display"] and "fallback_payload" in rule["display"]:
            buttons.append(
                {"title": dispatcher.retrieve_template(rule["display"]["fallback_title"])["text"],
                 "payload": rule["display"]["fallback_payload"]
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
