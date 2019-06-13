from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import requests
import simplejson
from rasa.nlu.components import Component
from typing import Any, List, Optional, Text, Dict

from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.model import Metadata
from rasa.nlu.training_data import Message

logger = logging.getLogger(__name__)


class EntitiesFilter(Component):
    """Filter entities wrt intent"""

    name = "EntitiesFilter"
    provides = ["entities"]
    defaults = {
        "entities": {}
    }

    def __init__(self, component_config=None):
        # type: (Text, Optional[List[Text]]) -> None

        super(EntitiesFilter, self).__init__(component_config)

    @classmethod
    def create(
        cls, component_config: Dict[Text, Any], config: RasaNLUModelConfig
    ) -> 'EntitiesFilter':
        return cls(component_config)

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        # get intent
        intent = message.get("intent")
        if intent is None:
            logger.warn("No intent found")

        # get crf and duckling entities
        message_entities = message.get("entities")
        entities_to_filter = filter(lambda e: e["extractor"] in ["ner_crf", "ner_duckling_http"], message_entities)
        indices_to_remove = []
        for index, entity in enumerate(entities_to_filter):
            if intent["name"] in self.component_config["entities"].keys() and entity["entity"] not in self.component_config["entities"][intent["name"]]:
                indices_to_remove.append(index)

        for i in sorted(indices_to_remove, reverse=True):
            del message.get("entities")[i]

    @classmethod
    def load(cls,
             component_meta: Dict[Text, Any],
             model_dir: Text = None,
             model_metadata: Metadata = None,
             cached_component: Optional['EntitiesFilter'] = None,
             **kwargs: Any
             ) -> 'EntitiesFilter':
        return cls(component_meta)
