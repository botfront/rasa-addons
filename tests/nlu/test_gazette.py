from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.nlu.components.gazette import Gazette
from rasa.nlu.training_data.message import Message

from pytest import raises


def _get_instance(config=None, gazette=None):
    if config is None:
        config = {"entities": [{"name": "type"}]}

    if gazette is None:
        gazette = {
            "type": ["chinese", "restaurant", "something totally different"],
            "city": ["New York"],
        }

    return Gazette(component_config=config, gazette=gazette)


def _process_example(message, **kwargs):
    _get_instance(**kwargs).process(message)
    return message


def _get_example(config=None, gazette=None, primary=None):
    if primary is None:
        primary = {
            "entity": "type",
            "value": "chines",
            "start": 14,
            "end": 20,
            "extractor": "ner_crf",
        }
    return _process_example(
        Message(
            text="Looking for a chines restaurant in New York",
            data={
                "entities": [
                    primary,
                    {
                        "entity": "type",
                        "value": "restaurant",
                        "start": 21,
                        "end": 31,
                        "extractor": "ner_crf",
                    },
                    {
                        "entity": "city",
                        "value": "New York",
                        "start": 35,
                        "end": 43,
                        "extractor": "ner_crf",
                    },
                ]
            },
        ),
        config=config,
        gazette=gazette,
    )


def _test_entity(entity, expected_value, expected_matches):
    assert entity["value"] == expected_value
    if expected_matches:
        assert len(entity["gazette_matches"]) == expected_matches
    else:
        assert raises(KeyError, lambda x: x["gazette_matches"], entity)


def _assert_missing_entities(entities):
    assert len(entities) == 2


def test_fuzzy_matching():
    example = _get_example()

    # test the changed entity
    _test_entity(example.data["entities"][0], "chinese", 3)

    # test unchanged entity
    _test_entity(example.data["entities"][2], "New York", 0)


def test_activate_entities():
    example = _get_example({"entities": [{"name": "type"}, {"name": "city"}]})

    _test_entity(example.data["entities"][2], "New York", 1)


def test_extra_matches():
    example = _get_example({"entities": [{"name": "type"}], "max_num_suggestions": 1})

    _test_entity(example.data["entities"][0], "chinese", 1)


def test_no_show():
    example = _get_example(
        gazette={
            "type": ["chinese", "something totally different"],
            "city": ["New York"],
        }
    )

    _assert_missing_entities(example.data["entities"])


def test_mode_specification():
    example = _get_example(
        config={"entities": [{"name": "type", "mode": "ratio"}]},
        gazette={"type": ["chinese"]},
    )
    _test_entity(example.data["entities"][0], "chinese", 1)

    example = _get_example(
        config={"entities": [{"name": "type", "mode": "partial_ratio"}]},
        gazette={"type": ["chinese"]},
    )
    _test_entity(example.data["entities"][0], "chinese", 1)

    example = _get_example(
        config={"entities": [{"name": "type", "mode": "ratio"}]},
        gazette={"type": ["chinese and a whole bunch of other stuff", "restaurant"]},
    )
    _assert_missing_entities(example.data["entities"])

    example = _get_example(
        config={"entities": [{"name": "type", "mode": "partial_ratio"}]},
        gazette={"type": ["chinese and a whole bunch of other stuff"]},
    )
    _test_entity(
        example.data["entities"][0], "chinese and a whole bunch of other stuff", 1
    )

