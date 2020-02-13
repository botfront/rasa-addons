from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.nlu.components.sweeper import Sweeper
from rasa.nlu.training_data.message import Message
from pytest import raises


def test_entity_sweeper():
    entities = [
        {"entity": "cuisine", "value": "chinese", "start": 0, "end": 6},
        {"entity": "time", "value": "whatever", "start": 0, "end": 6},
    ]
    sweeper = Sweeper(component_config={"entity_names": ["time"]})
    message = Message("xxx", {"entities": entities})
    sweeper.process(message)
    assert len(message.get("entities")) == 1
    assert message.get("entities")[0]["entity"] == "cuisine"
