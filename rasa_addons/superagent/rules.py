import io
import re

import yaml
import logging

from rasa_core.events import ActionExecuted
from rasa_addons.superagent.input_validator import InputValidator

logger = logging.getLogger(__name__)


class Rules(object):
    def __init__(self, rules_file):
        data = self._load_yaml(rules_file)
        self.actions_to_ignore = ['action_listen', 'action_invalid_utterance']
        self.allowed_entities = data["allowed_entities"] if "allowed_entities" in data else {}
        self.intent_substitutions = data["intent_substitutions"] if "intent_substitutions" in data else []
        self.input_validation = InputValidator(data["input_validation"]) if "input_validation" in data else []

    def filter_entities(self, parse_data):

        if parse_data['intent']['name'] in self.allowed_entities.keys():
            filtered = list(filter(lambda ent: ent['entity'] in self.allowed_entities[parse_data['intent']['name']],
                              parse_data['entities']))
        else:
            filtered = parse_data['entities']

        if len(filtered) < len(parse_data['entities']):
            # logging first
            logger.warn("entity(ies) were removed from parse stories")
            parse_data['entities'] = filtered

    def substitute_intent(self, parse_data, tracker):
        previous_action = self._get_previous_action(tracker)
        if previous_action is None:
            return

        for rule in self.intent_substitutions:
            rule['unless'] = rule['unless'] if 'unless' in rule else []
            if re.match(rule['after'], previous_action):
                if parse_data['intent']['name'] not in rule['unless']:
                    logger.warn("intent '{}' was replaced with '{}'".format(parse_data['intent']['name'], rule['intent']))
                    parse_data['intent']['name'] = rule['intent']
                    parse_data.pop('intent_ranking', None)

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

    @staticmethod
    def _load_yaml(rules_file):
        with io.open(rules_file, 'r', encoding='utf-8') as stream:
            try:
                return yaml.load(stream)
            except yaml.YAMLError as exc:
                raise ValueError(exc)
