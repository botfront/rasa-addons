import io
import yaml
import re
from rasa_core.actions.action import Action
from rasa_core.events import ActionExecuted, ActionReverted


class InputValidator(object):
    def __init__(self, rules):
        self.rules = rules if rules is not None else []
        self.actions_to_ignore = ['action_listen', 'action_invalid_utterance']

    def ignore_action(self, action_name):
        self.actions_to_ignore.append(action_name)

    def find(self, after):
        for rule in self.rules:
            if re.match(rule['after'], after):
                return rule
        return None

    def get_error(self, parse_data, tracker):
        previous_action = self._get_previous_action(tracker)
        if previous_action is None:
            return None
        return self._get_error(parse_data, previous_action)

    def _get_error(self, parse_data, previous_action):
        rule = self.find(previous_action)
        if rule is None:
            return None
        for expected in rule['expected']:
            intent_ok = 'intents' not in expected or parse_data["intent"]["name"] in expected['intents']
            parse_entities = map(lambda e: e['entity'], parse_data['entities'])

            # ok if no entities are expected or if expected entities are a subset of parse_entities
            entities_ok = 'entities' not in expected or set(expected['entities']).issubset(parse_entities)
            if entities_ok and intent_ok:
                return None
        return rule['error_template']

    @staticmethod
    def _load_yaml(rules_file):
        with io.open(rules_file, 'r', encoding='utf-8') as stream:
            try:
                return yaml.load(stream)
            except yaml.YAMLError as exc:
                raise ValueError(exc)

    def _get_previous_action(self, tracker):
        action_listen_found = False
        for i in range(len(tracker.events) - 1, -1, -1):
            if i == 0:
                return None
            if type(tracker.events[i]) is ActionExecuted \
                    and action_listen_found is False \
                    and tracker.events[i].action_name not in self.actions_to_ignore:
                return tracker.events[i].action_name

        return None


class ActionInvalidUtterance(Action):
    def __init__(self, template):
        self.template = template

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_template(self.template)

        # utter error message
        latest_bot_message = {"text": tracker.latest_bot_utterance.text}

        # repeat previous question
        if tracker.latest_bot_utterance.data is not None:
            for key in tracker.latest_bot_utterance.data.keys():
                latest_bot_message[key] = tracker.latest_bot_utterance.data[key]

        dispatcher.utter_response(latest_bot_message)
        return [ActionReverted(), ActionReverted()]

    def name(self):
        return 'action_invalid_utterance'
