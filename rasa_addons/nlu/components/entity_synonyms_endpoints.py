from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import warnings

from builtins import str
from typing import Any, Dict, Optional, Text

from rasa.nlu.extractors.entity_synonyms import EntitySynonymMapper


class EntitySynonymBegin(EntitySynonymMapper):
    name = "EntitySynonymBegin"

    provides = ["entities"]

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None
        updated_entities = message.get("entities", [])[:]
        updated_entities.sort(key=lambda x: x["start"])
        self.replace_synonyms(updated_entities)

        def shift_entities(entities, shift):
            for e in entities:
                e["start"] += shift
                e["end"] += shift

        if len(updated_entities):
            for i, entity in enumerate(updated_entities):
                literal = message.text[entity["start"] : entity["end"]]
                value = entity["value"]
                if value != literal and isinstance(value, str):
                    entity["literal"] = literal
                    message.text = (
                        message.text[0 : entity["start"]]
                        + value
                        + message.text[entity["end"] :]
                    )
                    shift = len(value) - (entity["end"] - entity["start"])
                    entity["end"] = entity["start"] + len(value)
                    if len(updated_entities) > i + 1:  # more entities:
                        shift_entities(updated_entities[i + 1 :], shift)

        message.set("entities", updated_entities, add_to_output=True)


class EntitySynonymEnd(EntitySynonymMapper):
    name = "EntitySynonymEnd"

    provides = ["entities"]

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None
        updated_entities = message.get("entities", [])[:]
        updated_entities.sort(key=lambda x: x["start"])

        def shift_entities(entities, shift):
            for e in entities:
                e["start"] += shift
                e["end"] += shift

        for i, entity in enumerate(updated_entities):
            if "literal" in entity:
                message.text = (
                    message.text[0 : entity["start"]]
                    + entity["literal"]
                    + message.text[entity["end"] :]
                )
                shift = len(entity["literal"]) - (entity["end"] - entity["start"])
                entity["end"] = entity["start"] + len(entity["literal"])
                del entity["literal"]
                if len(updated_entities) > i + 1:  # more entities:
                    shift_entities(updated_entities[i + 1 :], shift)

        message.set("entities", updated_entities, add_to_output=True)
