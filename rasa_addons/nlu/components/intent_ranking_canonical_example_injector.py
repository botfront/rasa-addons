import os
import warnings

from typing import Any, Text, Dict, Optional, List

from rasa.nlu.components import Component
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.training_data import Message, TrainingData
from rasa.nlu.model import Metadata


class IntentRankingCanonicalExampleInjector(Component):
    """
        Will remember the first encountered intent/entity-value combination
        in the training data, and inject it under a "canonical" key in each
        member of intent_ranking.
    """

    name = "IntentRankingCanonicalExampleInjector"

    defaults = {}

    def __init__(
        self,
        component_config: Optional[Dict[Text, Any]] = None,
        canonicals: Optional[Dict] = {},
    ) -> None:

        super(IntentRankingCanonicalExampleInjector, self).__init__(component_config)
        self.canonicals = canonicals

    @staticmethod
    def generate_entity_pairs(entities):
        return frozenset((e.get("entity"), e.get("value")) for e in entities)

    def generate_canonicals(self, nlu_data):
        canonicals = {}
        for datum in nlu_data:
            intent, text, entities = (
                datum.get("intent", ""),
                datum.get("text", ""),
                datum.get("entities", []),
            )
            entities = self.generate_entity_pairs(entities)
            if intent not in canonicals:
                canonicals[intent] = {}
            if entities not in canonicals[intent]:
                canonicals[intent][entities] = text

        return canonicals

    def train(
        self, training_data: TrainingData, cfg: RasaNLUModelConfig, **kwargs: Any
    ) -> None:

        self.canonicals = self.generate_canonicals(training_data.training_examples)

    def get_canonical(self, intent, entities):
        if intent not in self.canonicals.keys():
            return None
        entities = self.generate_entity_pairs(entities)
        canonicals = self.canonicals[intent]
        if len(canonicals or {}) < 1:
            return None
        if entities in canonicals:
            return canonicals[entities]
        matches = sorted(
            canonicals.keys(), key=lambda k: len(k.symmetric_difference(entities)),
        )
        return canonicals[matches[0]]

    def process(self, message: Message, **kwargs: Any) -> None:
        intent_ranking, entities = (
            message.get("intent_ranking", []),
            message.get("entities", []),
        )

        for i in range(len(intent_ranking)):
            intent_ranking[i]["canonical"] = self.get_canonical(
                intent_ranking[i].get("name"), entities
            )

        message.set(
            "intent_ranking", intent_ranking, add_to_output=True,
        )

    @classmethod
    def load(
        cls,
        meta: Dict[Text, Any],
        model_dir: Text = None,
        model_metadata: Metadata = None,
        cached_component: Optional["IntentRankingCanonicalExampleInjector"] = None,
        **kwargs: Any
    ) -> "IntentRankingCanonicalExampleInjector":

        from rasa.utils.io import pickle_load

        file_name = meta.get("file")
        path = os.path.join(model_dir, file_name)

        if os.path.exists(path):
            return cls(meta, **pickle_load(path))
        else:
            return cls(meta)

    def persist(self, file_name: Text, model_dir: Text) -> Optional[Dict[Text, Any]]:

        from rasa.utils.io import pickle_dump

        file_name = file_name + ".pickle"
        path = os.path.join(model_dir, file_name)
        persisted = {"canonicals": self.canonicals}
        pickle_dump(path, persisted)

        return {"file": file_name}
