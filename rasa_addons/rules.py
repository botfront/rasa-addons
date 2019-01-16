import copy
import io
import logging
import copy
import re

import yaml
from rasa_core.events import ActionExecuted
from requests.exceptions import RequestException

from rasa_addons.disambiguation import Disambiguator
from rasa_addons.input_validation import InputValidator, ActionInvalidUtterance

logger = logging.getLogger(__name__)


class Rules(object):
    def __init__(self, rules_dict):
        self.rules_dict = {}
        self.input_validation = None
        self.allowed_entities = None
        self.intent_substitutions = None
        self.disambiguation_policy = None
        self.actions_to_ignore = ['action_listen', 'action_invalid_utterance']
        self.update(rules_dict)

    def update(self, rules_dict):
        self.rules_dict = rules_dict
        self.allowed_entities = rules_dict[
            "allowed_entities"] if rules_dict and "allowed_entities" in rules_dict else {}
        self.intent_substitutions = rules_dict[
            "intent_substitutions"] if rules_dict and "intent_substitutions" in rules_dict else []
        self.input_validation = InputValidator(
            rules_dict["input_validation"]) if rules_dict and "input_validation" in rules_dict else []
        self.disambiguation_policy = Disambiguator(
            rules_dict.get("disambiguation_policy", None) if rules_dict else None,
            rules_dict.get("fallback_policy", None) if rules_dict else None)

    def get(self):
        return self.rules_dict

    def interrupts(self, dispatcher, parse_data, tracker, run_action):
        parse_data['original_data'] = copy.deepcopy(parse_data)

        # fallback has precedence
        if self.disambiguation_policy.fallback(parse_data, tracker, dispatcher, run_action) or \
                self.disambiguation_policy.disambiguate(parse_data, tracker, dispatcher, run_action):
            return True

        self.run_swap_intent_rules(parse_data, tracker)

        self.filter_entities(parse_data)

        if self.input_validation:
            error_template = self.input_validation.get_error(parse_data, tracker)
            if error_template is not None:
                self._utter_error_and_roll_back(dispatcher, tracker, error_template, run_action)
                return True

        if {key: val for key, val in parse_data.items() if key != 'original_data'} == parse_data['original_data']:
            # Nothing has changed
            del parse_data['original_data']

    @staticmethod
    def _utter_error_and_roll_back(dispatcher, tracker, template, run_action):
        action = ActionInvalidUtterance(template)
        run_action(action, tracker, dispatcher)

    def filter_entities(self, parse_data):

        if parse_data['intent']['name'] in self.allowed_entities.keys():
            filtered = list(filter(lambda ent: ent['entity'] in self.allowed_entities[parse_data['intent']['name']],
                                   parse_data['entities']))
        else:
            filtered = parse_data['entities']

        if len(filtered) < len(parse_data['entities']):
            # logging first
            logger.warning("entity(ies) were removed from parse stories")
            parse_data['entities'] = filtered

    def run_swap_intent_rules(self, parse_data, tracker):
        # # don't do anything if no intent is present
        # if parse_data["intent"]["name"] is None or parse_data["intent"]["name"] == "":
        #     return

        previous_action = self._get_previous_action(tracker)

        for rule in self.intent_substitutions:
            if Rules._swap_intent(parse_data, previous_action, rule):
                break

    @staticmethod
    def _swap_intent(parse_data, previous_action, rule):
        # don't do anything if no intent is present
        # if parse_data["intent"]["name"] is None or parse_data["intent"]["name"] == "":
        #     return

        # for an after rule
        if previous_action and 'after' in rule and re.match(rule['after'], previous_action):
            return Rules._swap_intent_after(parse_data, rule)

        # for a general substitution
        elif 'after' not in rule:
            if rule['intent'] is None or parse_data['intent']['name'] is None:
                return
            if (rule['intent'] is None and parse_data['intent']['name'] is None) \
                    or (re.match(rule['intent'], parse_data['intent']['name'])):
                return Rules.swap_intent_with(parse_data, rule)

    @staticmethod
    def _swap_intent_after(parse_data, rule):
        rule['unless'] = rule['unless'] if 'unless' in rule else []
        if parse_data['intent']['name'] is None or parse_data['intent']['name'] not in rule['unless']:
            logger.debug(
                "intent '{}' was replaced with '{}'".format(parse_data['intent']['name'], rule['intent']))
            parse_data['intent']['name'] = rule['intent']
            parse_data['intent']['confidence'] = 1.0
            parse_data.pop('intent_ranking', None)
            return True

    @staticmethod
    def swap_intent_with(parse_data, rule):

        def format(text, parse_data):
            return text.format(intent=parse_data["intent"]["name"])

        pd_copy = copy.deepcopy(parse_data)
        parse_data['intent']['name'] = rule['with']
        parse_data['intent_ranking'] = [{"name": rule['with'], "confidence": 1.0}]
        logger.debug(
            "intent '{}' was replaced with '{}'".format(parse_data['intent']['name'], rule['with']))
        if 'entities' in rule and 'add' in rule["entities"]:
            for entity in rule["entities"]["add"]:
                if 'entities' not in parse_data:
                    parse_data['entities'] = []
                parse_data['entities'].append(
                    {"entity": format(entity["name"], pd_copy), "value": format(entity["value"], pd_copy)})
        return True

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

    @classmethod
    def load_from_remote(cls, endpoint):
        try:
            logger.debug("Requesting rules from server {}..."
                         "".format(endpoint.url))
            response = endpoint.request(method='get')

            if response.status_code in [204, 304]:
                logger.debug("Model server returned {} status code, indicating "
                             "that no new rules are available.".format(response.status_code))
                return None
            elif response.status_code == 404:
                logger.warning("Tried to fetch rules from server but got a 404 response")
                return None
            elif response.status_code != 200:
                logger.warning("Tried to fetch rules from server, but server response "
                               "status code is {}. We'll retry later..."
                               "".format(response.status_code))
            else:
                rules = response.json()
                return Rules(rules)

        except RequestException as e:
            logger.warning("Tried to fetch rules from server, but couldn't reach "
                           "server. We'll retry later... Error: {}."
                           "".format(e))

    @classmethod
    def load_from_file(cls, rules_file):
        try:
            logger.debug('Loading rules from the {} file'.format(rules_file))
            return Rules(Rules._load_yaml(rules_file))
        except Exception as e:
            raise e
