from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import requests
import logging
import json

from typing import Any

from rasa.nlu.components import Component
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.training_data.message import Message

logger = logging.getLogger(__name__)


class Sweeper(Component):
    name = 'Sweeper'

    defaults = {
        'entity_names': []
    }

    def __init__(self, component_config=None):
        # type: (RasaNLUModelConfig) -> None
        super(Sweeper, self).__init__(component_config)

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        message_entities = message.get("entities")
        sweeped_entities = list(filter(lambda e: e["entity"] not in self.component_config["entity_names"], message_entities))
        message.set("entities", sweeped_entities)

