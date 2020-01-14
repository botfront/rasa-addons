import json
import logging
import os
from typing import Any, List, Text, Dict
import rasa.utils.io
import re
from rasa.core.actions.action import ACTION_LISTEN_NAME

from rasa.core.domain import Domain
from rasa.core.policies.policy import Policy, confidence_scores_for
from rasa.core.events import SlotSet
from rasa.core.trackers import DialogueStateTracker

logger = logging.getLogger(__name__)

class BotfrontDisambiguationPolicy(Policy):

    @staticmethod
    def _standard_featurizer():
        return None

    def __init__(
        self,
        priority: int = 4,
        disambiguation_trigger: str = "$0 < 2 * $1",
        fallback_trigger: float = 0.30,
        deny_suggestions: Text = "deny_suggestions",
        excluded_intents: List = [], # list of regex e.g ["^chitchat\..*", ...]
        intent_mappings: Dict[Text, Dict[Text, Text]] = {}, # {"basics.yes": {"en": "Yes", "fr": "Oui"}}
        n_suggestions: int = 3,
        disambiguation_title: Dict[Text, Text] = {
            "en": "Sorry, I'm not sure I understood. Did you mean..."
        }
    ) -> None:
        super(BotfrontDisambiguationPolicy, self).__init__(priority=priority)

        self.disambiguation_trigger = disambiguation_trigger
        self.fallback_trigger = fallback_trigger
        self.fallback_default_confidence = 0.30
        self.disambiguation_action = "action_botfront_disambiguation"
        self.disambiguation_followup_action = "action_botfront_disambiguation_followup"
        self.fallback_action = "action_botfront_fallback" # utter_fallback
        self.deny_suggestions = deny_suggestions
        self.excluded_intents = excluded_intents + [self.deny_suggestions]
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

    def generate_disambiguation_message(self, intent_ranking, entities, language):
        intent_names = [intent.get('name', '')
                        for intent in intent_ranking]
        intent_names = [intent for intent in intent_names if len([
                        excl for excl in self.excluded_intents if
                        re.compile(excl).fullmatch(intent) != None]) < 1][:self.n_suggestions]

        mapped_intents = [(name, self.fill_entity(
                            self.intent_mappings.get(name, {language: name})[language],
                            entities
                          )) for name in intent_names]

        entities_json = json.dumps({e.get("entity"): e.get("value") for e in entities}) if len(entities) > 0 else ""

        message_title = self.disambiguation_title[language]
        deny_text = self.intent_mappings.get(self.deny_suggestions, {"en": "Something else"})[language]

        buttons = []
        for intent in mapped_intents:
            buttons.append({'title': intent[1],
                            'type': 'postback',
                            'payload': '/{}{}'.format(intent[0], entities_json)})

        buttons.append({'title': deny_text,
                        'type': 'postback',
                        'payload': '/{}'.format(self.deny_suggestions)})
        return {
            "title": message_title,
            "buttons": buttons
        }
    
    @staticmethod
    def fill_entity(template, entities):
        title = template
        for e in entities:
            title = title.replace('{' + e.get("entity") + '}', e.get("value"))
        title = re.sub(r'{.*?}', r'', title)
        return title

    @staticmethod
    def set_slot(tracker, message):
        if len(message["buttons"]) < 2: return None # abort if only deny_suggestions button would be shown
        try:
            tracker.update(SlotSet("disambiguation_message", value=message))
            result = message
        except Exception as e:
            logger.error("Could not set message slot: {}".format(e))
            result = None
        return result

    @staticmethod
    def _should_disambiguate(intent_ranking, trigger):
        import re
        # pattern to match $0, $1, $2, ... and returning 0, 1, 2,... in match groups
        pattern = re.compile(r"\$(\d)")
        eval_string = trigger
        # matches: an array of intents indices to consider in intent_ranking
        matches = re.findall(pattern, trigger)
        for i in matches:
            # if not enough intents in ranking to apply the rule, policy rule can't be triggered
            if int(i) >= len(intent_ranking): return False
            eval_string = re.sub(r'\$' + i, str(intent_ranking[int(i)]["confidence"]), eval_string)

        return eval(eval_string, {'__builtins__': {}})
    
    @staticmethod
    def _should_fallback(intent_ranking, trigger):
        bonified_ranking = intent_ranking + [{"confidence": 0}]
        return bonified_ranking[0]["confidence"] < trigger

    def _is_user_input_expected(self, tracker: DialogueStateTracker) -> bool:
        return tracker.latest_action_name in [
            self.fallback_action,
            self.disambiguation_action
        ]
    
    def _have_options_been_suggested(self, tracker: DialogueStateTracker) -> bool:
        return tracker.last_executed_action_has(self.disambiguation_action)

    def predict_action_probabilities(
        self, tracker: DialogueStateTracker, domain: Domain
    ) -> List[float]:

        parse_data = tracker.latest_message.parse_data
        metadata = tracker.latest_message.metadata
        entities = parse_data.get("entities", [])
        language = metadata.get("language", "en")
        intent_ranking = parse_data.get('intent_ranking', [])
        can_apply = tracker.latest_action_name == ACTION_LISTEN_NAME
        should_fallback = can_apply and self._should_fallback(intent_ranking, self.fallback_trigger)
        should_disambiguate = can_apply and self._should_disambiguate(
            intent_ranking, self.disambiguation_trigger
        )

        if self._is_user_input_expected(tracker):
            # Shut up and listen
            result = confidence_scores_for(ACTION_LISTEN_NAME, 1.0, domain)

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
            disambiguation_message = self.generate_disambiguation_message(intent_ranking, entities, language)
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

        config_file = os.path.join(path, "botfront_disambiguation_policy.json")
        meta = {
            "priority": self.priority,
            "disambiguation_trigger": self.disambiguation_trigger,
            "fallback_trigger": self.fallback_trigger,
            "deny_suggestions": self.deny_suggestions,
            "excluded_intents": self.excluded_intents,
            "n_suggestions": self.n_suggestions,
            "intent_mappings": self.intent_mappings,
            "disambiguation_title": self.disambiguation_title
        }
        rasa.utils.io.create_directory_for_file(config_file)
        rasa.utils.io.dump_obj_as_json_to_file(config_file, meta)

    @classmethod
    def load(cls, path: Text) -> "BotfrontDisambiguationPolicy":
        meta = {}
        if os.path.exists(path):
            meta_path = os.path.join(path, "botfront_disambiguation_policy.json")
            if os.path.isfile(meta_path):
                meta = json.loads(rasa.utils.io.read_file(meta_path))

        return cls(**meta)
