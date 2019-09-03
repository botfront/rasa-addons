import json
import logging
import os
from typing import Any, List, Text, Dict
import rasa.utils.io

from rasa.core import utils
from rasa.core.domain import Domain
from rasa.core.policies.policy import Policy, confidence_scores_for
from rasa.core.events import SlotSet
from rasa.core.trackers import DialogueStateTracker

logger = logging.getLogger(__name__)

class DisambiguationPolicy(Policy):
    """Policy which predicts fallback actions.

    A fallback can be triggered by a low confidence score on a
    NLU prediction or by a low confidence score on an action
    prediction. """

    @staticmethod
    def _standard_featurizer():
        return None

    def __init__(
        self,
        priority: int = 4,
        disambiguation_trigger: str = "$0 < 2 * $1",
        fallback_trigger: float = 0.30,
        excluded_intents: List = [], # list of regex e.g ["chitchat.*", "basics.*",...]
        intent_mappings: Dict[Text, Dict[Text, Text]] = {}, # {"basics.yes": {"en": "Yes", "fr": "Oui"}}
        n_suggestions: int = 3,
        disambiguation_title: Dict[Text, Text] = {
            "en": "Sorry, I'm not sure I understood. Did you mean..."
        }
    ) -> None:
        super(DisambiguationPolicy, self).__init__(priority=priority)

        self.disambiguation_trigger = disambiguation_trigger
        self.fallback_trigger = fallback_trigger
        self.fallback_default_confidence = 0.30
        self.disambiguation_action = "action_botfront_disambiguation"
        self.disambiguation_followup_action = "action_botfront_disambiguation_followup"
        self.disambiguation_action_denial = "action_botfront_disambiguation_denial" # utter_ask_rephrase
        self.fallback_action = "action_botfront_fallback" # utter_fallback
        self.deny_suggestion_intent_name = "deny_suggestions"
        self.excluded_intents = excluded_intents + [self.deny_suggestion_intent_name]
        self.n_suggestions = n_suggestions
        self.intent_mappings = intent_mappings
        self.disambiguation_title = disambiguation_title

    def train(
        self,
        training_trackers: List[DialogueStateTracker],
        domain: Domain,
        **kwargs: Any
    ) -> None:
        pass

    def generate_disambiguation_message(self, tracker):
        language = tracker.latest_message.parse_data.get('language', 'en')
        intent_ranking = tracker.latest_message.parse_data.get('intent_ranking', [])
        intent_ranking = [intent for intent in intent_ranking
                          if intent.get('name', '') not in self.excluded_intents][:self.n_suggestions]
                              
        first_intent_names = [intent.get('name', '')
                              for intent in intent_ranking]

        mapped_intents = [(name, self.intent_mappings.get(name, {language: name})[language])
                          for name in first_intent_names]

        entities = tracker.latest_message.parse_data.get("entities", [])
        entities_json, entities_text = self.get_formatted_entities(entities)

        message_title = self.disambiguation_title["en"]
        deny_text = self.intent_mappings.get(self.deny_suggestion_intent_name, {"en": "Something else"})[language]

        buttons = []
        for intent in mapped_intents:
            buttons.append({'title': intent[1] + entities_text,
                            'payload': '/{}{}'.format(intent[0],
                                                      entities_json)})

        buttons.append({'title': deny_text,
                        'payload': '/{}'.format(self.deny_suggestion_intent_name)})
        return {
            "title": message_title,
            "buttons": buttons
        }

    @staticmethod
    def set_slot(tracker, message):
        try:
            tracker.update(SlotSet("disambiguation_message", value=message))
            result = message
        except Exception as e:
            logger.error("Could not set message slot: {}".format(e))
            result = None
        return result

    @staticmethod
    def get_formatted_entities(entities: List[Dict[str, Any]]) -> (Text, Text):
        key_value_entities = {}
        for e in entities:
            key_value_entities[e.get("entity")] = e.get("value")
        entities_json = ""
        entities_text = ""
        if len(entities) > 0:
            entities_json = json.dumps(key_value_entities)
            entities_text = ["'{}': '{}'".format(k, key_value_entities[k])
                            for k in key_value_entities]
            entities_text = ", ".join(entities_text)
            entities_text = " ({})".format(entities_text)

        return entities_json, entities_text

    @staticmethod
    def _should_disambiguate(parse_data, trigger):
        #if not len(parse_data["intent_ranking"]): return False
        import re
        # pattern to match $0, $1, $2, ... and returning 0, 1, 2,... in match groups
        pattern = re.compile(r"\$(\d)")
        eval_string = trigger
        # matches: an array of intents indices to consider in intent_ranking
        matches = re.findall(pattern, trigger)
        for i in matches:
            # if not enough intents in ranking to apply the rule, policy rule can't be triggered
            if int(i) >= len(parse_data["intent_ranking"]): return False
            eval_string = re.sub(r'\$' + i, str(parse_data["intent_ranking"][int(i)]["confidence"]), eval_string)

        return eval(eval_string, {'__builtins__': {}})

    def _is_user_input_expected(self, tracker: DialogueStateTracker) -> bool:
        return tracker.latest_action_name in [
            self.fallback_action,
            self.disambiguation_action,
            self.disambiguation_action_denial
        ]
    
    def _have_options_been_suggested(self, tracker: DialogueStateTracker) -> bool:
        return tracker.last_executed_action_has(self.disambiguation_action)

    def _has_user_denied(self, parse_data) -> bool:
        last_intent = parse_data["intent"].get("name", None)
        return last_intent == self.deny_suggestion_intent_name

    def predict_action_probabilities(
        self, tracker: DialogueStateTracker, domain: Domain
    ) -> List[float]:

        parse_data = tracker.latest_message.parse_data
        can_apply = tracker.latest_action_name == "action_listen"
        should_fallback = can_apply and parse_data["intent"]["confidence"] < self.fallback_trigger
        should_disambiguate = can_apply and self._should_disambiguate(
            parse_data, self.disambiguation_trigger
        )

        if self._is_user_input_expected(tracker):
            # Shut up and listen
            result = confidence_scores_for("action_listen", 1.0, domain)

        elif self._has_user_denied(parse_data):
            logger.debug("User '{}' denied suggested intents.".format(tracker.sender_id))
            result = confidence_scores_for(self.disambiguation_action_denial, 1.0, domain)

        elif should_fallback:
            logger.debug("Triggering fallback")
            result = confidence_scores_for(self.fallback_action, 1.0, domain)
        
        elif self._have_options_been_suggested(tracker):
            if not should_disambiguate:
                logger.debug("Successfully disambiguated")
                result = confidence_scores_for(self.disambiguation_followup_action, 1.0, domain)
            else:
                logger.debug("Will not disambiguate a second time so fast -- triggering fallback")
                result = confidence_scores_for(self.fallback_action, 1.0, domain)

        elif should_disambiguate:
            logger.debug("Triggering disambiguation")
            disambiguation_message = self.generate_disambiguation_message(tracker)
            slot_set = self.set_slot(tracker, disambiguation_message)
            if slot_set:
                result = confidence_scores_for(self.disambiguation_action, 1.0, domain)
            else:
                result = confidence_scores_for(self.fallback_action, 1.0, domain)

        else:
            # Nothing to see here; setting fallback to default confidence
            result = confidence_scores_for(self.fallback_action, self.fallback_default_confidence, domain)

        return result

    def persist(self, path: Text) -> None:
        """Persists the policy to storage."""

        config_file = os.path.join(path, "disambiguation_policy.json")
        meta = {
            "priority": self.priority,
            "disambiguation_trigger": self.disambiguation_trigger,
            "fallback_trigger": self.fallback_trigger,
            "excluded_intents": self.excluded_intents,
            "n_suggestions": self.n_suggestions,
            "intent_mappings": self.intent_mappings,
            "disambiguation_title": self.disambiguation_title
        }
        rasa.utils.io.create_directory_for_file(config_file)
        utils.dump_obj_as_json_to_file(config_file, meta)

    @classmethod
    def load(cls, path: Text) -> "DisambiguationPolicy":
        meta = {}
        if os.path.exists(path):
            meta_path = os.path.join(path, "disambiguation_policy.json")
            if os.path.isfile(meta_path):
                meta = json.loads(rasa.utils.io.read_file(meta_path))

        return cls(**meta)
