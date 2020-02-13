from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.nlu.components.entity_synonyms_endpoints import (
    EntitySynonymBegin,
    EntitySynonymEnd,
)
from rasa.nlu.training_data.message import Message

from pytest import raises


def _add_extractor(entity):
    entity["extractor"] = "ner_crf"
    return entity


def test_entity_synonyms():
    entities = [
        {"entity": "test", "value": "chines", "start": 0, "end": 6},
        {"entity": "test", "value": "chinese", "start": 0, "end": 6},
        {"entity": "test", "value": "china", "start": 0, "end": 6},
    ]
    ent_synonyms = {"chines": "chinese", "NYC": "New York City"}
    EntitySynonymBegin(synonyms=ent_synonyms).replace_synonyms(entities)
    assert len(entities) == 3
    assert entities[0]["value"] == "chinese"
    assert entities[1]["value"] == "chinese"
    assert entities[2]["value"] == "china"


def test_entity_synonyms_substitute():
    example = Message(
        text="Looking for a chines restaurant in New York",
        data={
            "entities": [
                {"entity": "type", "value": "chinese", "start": 14, "end": 20},
                {"entity": "city", "value": "New York", "start": 35, "end": 43},
            ]
        },
    )
    ent_synonyms = {"chines": "chinese", "new york": "NYC"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)
    assert example.text == "Looking for a chinese restaurant in NYC"


def test_entity_synonyms_substitute_one_entity():
    example = Message(
        text="Looking for a chines restaurant",
        data={
            "entities": [{"entity": "type", "value": "chinese", "start": 14, "end": 20}]
        },
    )
    ent_synonyms = {"chines": "chinese"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)

    assert example.text == "Looking for a chinese restaurant"
    e_type = list(filter(lambda e: e["entity"] == "type", example.get("entities")))[0]

    assert e_type["start"] == 14
    assert e_type["end"] == 21


def test_entity_synonyms_substitute_two_entity():
    example = Message(
        text="Looking for a chines restaurant in New York tomorrow",
        data={
            "entities": [
                {"entity": "type", "value": "chinese", "start": 14, "end": 20},
                {"entity": "city", "value": "New York", "start": 35, "end": 43},
            ]
        },
    )
    ent_synonyms = {"chines": "chinese", "new york": "NYC"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)

    assert example.text == "Looking for a chinese restaurant in NYC tomorrow"
    e_type = list(filter(lambda e: e["entity"] == "type", example.get("entities")))[0]
    e_city = list(filter(lambda e: e["entity"] == "city", example.get("entities")))[0]

    assert e_type["start"] == 14
    assert e_type["end"] == 21
    assert e_city["start"] == 36
    assert e_city["end"] == 39


def test_entity_synonyms_substitute_three_entity():
    example = Message(
        text="Looking for a chines restaurant in New York tomorrow for three people",
        data={
            "entities": [
                {"entity": "type", "value": "chines", "start": 14, "end": 20},
                {"entity": "city", "value": "New York", "start": 35, "end": 43},
                {"entity": "count", "value": "three", "start": 57, "end": 62},
            ]
        },
    )
    ent_synonyms = {"chines": "chinese", "new york": "NYC", "three": "3"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)

    assert (
        example.text == "Looking for a chinese restaurant in NYC tomorrow for 3 people"
    )
    e_type = list(filter(lambda e: e["entity"] == "type", example.get("entities")))[0]
    e_city = list(filter(lambda e: e["entity"] == "city", example.get("entities")))[0]
    e_count = list(filter(lambda e: e["entity"] == "count", example.get("entities")))[0]

    assert e_type["start"] == 14
    assert e_type["end"] == 21
    assert e_city["start"] == 36
    assert e_city["end"] == 39

    assert e_count["start"] == 53
    assert e_count["end"] == 54


def test_entity_synonyms_substitute_and_replace():
    initial_text = (
        "Looking for a chines restaurant in New York tomorrow for three people"
    )
    initial_entities = [
        {"entity": "type", "value": "chines", "start": 14, "end": 20},
        {"entity": "city", "value": "New York", "start": 35, "end": 43},
        {"entity": "count", "value": "three", "start": 57, "end": 62},
    ]

    example = Message(text=initial_text, data={"entities": initial_entities})
    ent_synonyms = {"chines": "chinese", "new york": "NYC", "three": "3"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)
    EntitySynonymEnd().process(example)


def test_entity_synonyms_substitute_and_replace_w_insertions():
    text_initial = (
        "Looking for a chines restaurant in New York tomorrow for three people"
    )
    initial_entities = [
        {"entity": "type", "value": "chines", "start": 14, "end": 20},
        {"entity": "city", "value": "New York", "start": 35, "end": 43},
        {"entity": "count", "value": "three", "start": 57, "end": 62},
    ]

    example = Message(text=text_initial, data={"entities": initial_entities})
    ent_synonyms = {"chines": "chinese", "new york": "NYC", "three": "3"}
    EntitySynonymBegin(synonyms=ent_synonyms).process(example)

    # import IPython
    # IPython.embed()
    example.data["entities"].extend(
        [
            {"entity": "action", "value": "Looking", "start": 0, "end": 7},
            {"entity": "place", "value": "restaurant", "start": 22, "end": 32},
            {"entity": "species", "value": "people", "start": 55, "end": 61},
        ]
    )

    EntitySynonymEnd().process(example)

    def has_changed(entity):
        return entity["value"] != example.text[entity["start"] : entity["end"]]

    assert example.text == text_initial

    changed_entities = filter(has_changed, example.data["entities"])
    # Check the unchanged entities match value <-> text[start:end]
    assert len(list(changed_entities)) == 3
    # Check the changed entities are reverted properly
    for initial, entity in zip(initial_entities, changed_entities):
        assert raises(KeyError, lambda x: print(x["literal"]), entity)
        assert entity["start"] == initial["start"]
        assert entity["end"] == initial["end"]
