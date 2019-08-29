import json
import logging
import os
from typing import Any, List, Text, Dict

from rasa.core.actions.action import ACTION_LISTEN_NAME
# from schema import Schema, And, Optional
import rasa.utils.io

from rasa.core import utils
from rasa.core.domain import Domain
from rasa.core.policies.policy import Policy
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
        fallback_trigger: str = "$0 <= 0.30",
        disambiguation_action_name: Text = "action_default_disambiguation",
        fallback_action_name: Text = "action_default_fallback",
        exclude_intents: List = [], # list of regex e.g ["chitchat.*", "basics.*",...]

    ) -> None:
        """Create a new Fallback policy.

        Args:
            core_threshold: if NLU confidence threshold is met,
                predict fallback action with confidence `core_threshold`.
                If this is the highest confidence in the ensemble,
                the fallback action will be executed.
            nlu_threshold: minimum threshold for NLU confidence.
                If intent prediction confidence is lower than this,
                predict fallback action with confidence 1.0.
            fallback_action_name: name of the action to execute as a fallback
        """
        super(DisambiguationPolicy, self).__init__(priority=priority)


        self.disambiguation_action_name = disambiguation_action_name
        self.fallback_action_name = fallback_action_name
        self.disambiguation_trigger = disambiguation_trigger
        self.fallback_trigger = fallback_trigger

    def train(
        self,
        training_trackers: List[DialogueStateTracker],
        domain: Domain,
        **kwargs: Any
    ) -> None:
        """Does nothing. This policy is deterministic."""

        print("train")

    def should_disambiguate(self, parse_data, last_action_name):
        if not self.disambiguation_trigger or "intent_ranking" not in parse_data:
            return False

        return (
            last_action_name == ACTION_LISTEN_NAME
            and self.is_triggered(parse_data, self.disambiguation_trigger)
            and not self.is_triggered(parse_data, self.fallback_trigger)
            )

    @staticmethod
    def is_triggered(parse_data, trigger):
        import re
        # pattern to match $0, $1, $2, ... and returning 0, 1, 2,... in match groups
        pattern = re.compile(r"\$(\d)")
        eval_string = trigger
        # matches: an array of intents indices to consider in intent_ranking
        matches = re.findall(pattern, trigger)
        for i in matches:
            # if not enough intents in ranking to apply the rule, policy rule can't be triggered
            if int(i) >= len(parse_data["intent_ranking"]):
                return False
            eval_string = re.sub(r'\$' + i, str(parse_data["intent_ranking"][int(i)]["confidence"]), eval_string)

        return len(parse_data["intent_ranking"]) and eval(eval_string, {'__builtins__': {}})

    def should_fallback(
        self, parse_data, last_action_name
    ) -> bool:
        """Checks if fallback action should be predicted.

        Checks for:
        - predicted NLU confidence is lower than ``nlu_threshold``
        - last action is action listen
        """

        return (
                last_action_name == ACTION_LISTEN_NAME
                and self.is_triggered(parse_data, self.fallback_trigger)
        )

    def disambiguation_scores(self, domain, disambiguation_score=1.0):
        """Prediction scores used if a fallback is necessary."""

        result = [0.0] * domain.num_actions
        idx = domain.index_for_action(self.disambiguation_action_name)
        result[idx] = disambiguation_score
        return result

    def fallback_scores(self, domain, fallback_score=1.0):
        """Prediction scores used if a fallback is necessary."""

        result = [0.0] * domain.num_actions
        idx = domain.index_for_action(self.fallback_action_name)
        result[idx] = fallback_score
        return result

    def predict_action_probabilities(
        self, tracker: DialogueStateTracker, domain: Domain
    ) -> List[float]:
        """Predicts a fallback action.

        The fallback action is predicted if the NLU confidence is low
        or no other policy has a high-confidence prediction.
        """

        nlu_data = tracker.latest_message.parse_data

        if tracker.latest_action_name == self.disambiguation_action_name:
            result = [0.0] * domain.num_actions
            idx = domain.index_for_action(ACTION_LISTEN_NAME)
            result[idx] = 1.0

        elif self.should_disambiguate(nlu_data, tracker.latest_action_name):
            logger.debug("Disambiguation triggered")

            result = self.disambiguation_scores(domain)

        elif self.should_fallback(nlu_data, tracker.latest_action_name):
            logger.debug("Fallback triggered")

            result = self.fallback_scores(domain)

        return result

    def persist(self, path: Text) -> None:
        """Persists the policy to storage."""

        config_file = os.path.join(path, "disambiguation_policy.json")
        meta = {
            "priority": self.priority,
            "fallback_trigger": self.disambiguation_trigger,
            "disambiguation_trigger": self.disambiguation_trigger,
            "disambiguation_action_name": self.disambiguation_action_name,
            "fallback_action_name": self.fallback_action_name,
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
