import os
import pytest
from rasa_addons.superagent.disambiguator import Disambiguator, ActionDisambiguate, ActionFallback
from rasa_addons.superagent.rules import Rules
from rasa_addons.utils import load_yaml
from schema import SchemaError
from rasa_addons.tests import TestNLG as StubNLG


ROOT_PATH = os.path.join(os.getcwd(), 'tests')


class StubDispatcher(object):

    def __init__(self):
        self.nlg = StubNLG(None)
        self.output_channel = None

class StubTracker(object):
    pass

tracker = StubTracker()

"""disambiguation-only tests"""

def test_disamb_trigger_wrong_format():
    with pytest.raises(SchemaError) as e:
        Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator3.yaml')['disambiguation_policy'])


def test_disamb_trigger1():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.5}]
    }
    result = disambiguator.should_disambiguate(parse_data)
    assert result is True

def test_disamb_trigger2():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }
    result = disambiguator.should_disambiguate(parse_data)
    assert result is False


def test_disamb_buttons_with_fallback():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }

    expected = {
        "text": "utter_disamb_text",
        "buttons": [{
            "title": "utter_disamb_intentA",
            "payload": "/intentA"
        }, {
            "title": "utter_disamb_intentB",
            "payload": "/intentB"
        }, {
            "title": "utter_fallback",
            "payload": "/fallback"
        }]
    }

    dispatcher = StubDispatcher()
    intents = disambiguator.get_intent_names(parse_data)
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
                                                         disambiguator.get_payloads(parse_data, intents),
                                                         intents,
                                                         tracker) == expected


def test_buttons_without_fallback():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }

    expected = {
        "text": "utter_disamb_text",
        "buttons": [{
            "title": "utter_disamb_intentA",
            "payload": "/intentA"
        }, {
            "title": "utter_disamb_intentB",
            "payload": "/intentB"
        }]
    }

    dispatcher = StubDispatcher()
    intents = disambiguator.get_intent_names(parse_data)
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
                                                         disambiguator.get_payloads(parse_data, intents),
                                                         intents,
                                                         tracker) == expected


def test_disamb_with_entities():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}],
        "entities": [{"entity": "entity1", "value": "value1"}]
    }

    expected = {
        "text": "utter_disamb_text",
        "buttons": [{
            "title": "utter_disamb_intentA",
            "payload": "/intentA{\"entity1\": \"value1\"}"
        }, {
            "title": "utter_disamb_intentB",
            "payload": "/intentB{\"entity1\": \"value1\"}"
        }]
    }
    dispatcher = StubDispatcher()
    intents = disambiguator.get_intent_names(parse_data)
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
                                                         disambiguator.get_payloads(parse_data, intents),
                                                         intents,
                                                         tracker) == expected


def test_disamb_does_not_trigger_when_data_is_missing_in_parse_data():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

    parse_data = {

    }
    assert disambiguator.should_disambiguate(parse_data) is False

def test_disamb_does_not_trigger_when_intent_is_null():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

    parse_data = {  
        "intent": {
            "name": None,
            "confidence": 0.0
        },
        "entities": [],
        "intent_ranking": []
    }

    assert disambiguator.should_disambiguate(parse_data) is False

def test_disamb_exclude_exact():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator10.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.4}, {"name": "intentB", "confidence": 0.3}, {"name": "intentC", "confidence": 0.3}]
    }

    expected = {
        "text": "utter_disamb_text",
        "buttons": [{
            "title": "utter_disamb_intentA",
            "payload": "/intentA"
        }, {
            "title": "utter_disamb_intentC",
            "payload": "/intentC"
        }, {
            "title": "utter_fallback",
            "payload": "/fallback"
        }]
    }

    dispatcher = StubDispatcher()
    intents = disambiguator.get_intent_names(parse_data)
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
                                                         disambiguator.get_payloads(parse_data, intents),
                                                         intents,
                                                         tracker) == expected

def test_disamb_exclude_regex():
    disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator11.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "chitchat.insults", "confidence": 0.3}, 
                            {"name": "intentA", "confidence": 0.2}, 
                            {"name": "chitchat.this_is_bad", "confidence": 0.2}, 
                            {"name": "basics.yes", "confidence": 0.15},
                            {"name": "intentB", "confidence": 0.15}],
        "entities": [{"entity": "entity1", "value": "value1"}]
    }

    expected = {
        "text": "utter_disamb_text",
        "buttons": [{
            "title": "utter_disamb_intentA",
            "payload": "/intentA{\"entity1\": \"value1\"}"
        }, {
            "title": "utter_disamb_intentB",
            "payload": "/intentB{\"entity1\": \"value1\"}"
        }, {
            "title": "utter_fallback",
            "payload": "/fallback"
        }]
    }

    dispatcher = StubDispatcher()
    intents = disambiguator.get_intent_names(parse_data)
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
                                                         disambiguator.get_payloads(parse_data, intents),
                                                         intents,
                                                         tracker) == expected

"""fallback-only tests"""

def test_fallback_trigger_wrong_format():
    with pytest.raises(SchemaError) as e:
        Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator5.yaml')['fallback_policy'])


def test_fallback_trigger1():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator6.yaml')['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.49}, {"name": "intentB", "confidence": 0.3}]
    }
    result = disambiguator.should_fallback(parse_data)
    assert result is True

def test_fallback_trigger2():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator6.yaml')['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }
    result = disambiguator.should_fallback(parse_data)
    assert result is False


def test_fallback_buttons_with_fallback():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator6.yaml')['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.49}, {"name": "intentB", "confidence": 0.3}]
    }

    expected = {
        "text": "utter_fallback_intro",
        "buttons": [{
            "title": "utter_fallback_yes",
            "payload": "/fallback"
        }, {
            "title": "utter_fallback_no",
            "payload": "/restart"
        }]
    }

    dispatcher = StubDispatcher()
    assert ActionFallback.get_fallback_message(dispatcher, disambiguator.fallback_rule, tracker) == expected

def test_fallback_buttons_without_fallback():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator7.yaml')['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.49}, {"name": "intentB", "confidence": 0.3}]
    }

    expected = {
        "text": "utter_fallback_intro"
    }

    dispatcher = StubDispatcher()
    assert ActionFallback.get_fallback_message(dispatcher, disambiguator.fallback_rule, tracker) == expected


def test_fallback_does_not_trigger_when_data_is_missing_in_parse_data():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator7.yaml')['fallback_policy'])

    parse_data = {

    }
    assert disambiguator.should_fallback(parse_data) is False

def test_fallback_does_not_trigger_when_intent_is_null():
    disambiguator = Disambiguator(fallback_rule=load_yaml('./tests/disambiguator/test_disambiguator7.yaml')['fallback_policy'])

    parse_data = {  
        "intent": {
            "name": "",
            "confidence": 0.0
        },
        "entities": [],
        "intent_ranking": []
    }

    assert disambiguator.should_fallback(parse_data) is False

"""disambiguation and fallback tests"""


def test_disamb_and_fallback_trigger_wrong_format():
    with pytest.raises(SchemaError) as e:
        rules = load_yaml('./tests/disambiguator/test_disambiguator8.yaml')
        disambiguator = Disambiguator(disamb_rule=rules['disambiguation_policy'], 
                                    fallback_rule=rules['fallback_policy'])


def test_disamb_and_fallback_trigger_any1():
    rules = load_yaml('./tests/disambiguator/test_disambiguator9.yaml')
    disambiguator = Disambiguator(disamb_rule=rules['disambiguation_policy'],
                                fallback_rule=rules['fallback_policy'])
    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.4}]
    }

    result = disambiguator.should_fallback(parse_data) or disambiguator.should_disambiguate(parse_data)
    assert result is True

def test_disamb_and_fallback_trigger_any2():
    rules = load_yaml('./tests/disambiguator/test_disambiguator9.yaml')
    disambiguator = Disambiguator(disamb_rule=rules['disambiguation_policy'],
                                fallback_rule=rules['fallback_policy'])
    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }

    result = disambiguator.should_fallback(parse_data) or disambiguator.should_disambiguate(parse_data)
    assert result is False


def test_disamb_and_fallback_trigger_both():
    rules = load_yaml('./tests/disambiguator/test_disambiguator9.yaml')
    disambiguator = Disambiguator(disamb_rule=rules['disambiguation_policy'],
                                fallback_rule=rules['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.49}, {"name": "intentB", "confidence": 0.4}]
    }
    # fallback has precedence and short-circuits disamb in the actual program flow as per rules.py
    result = disambiguator.should_fallback(parse_data) and disambiguator.should_disambiguate(parse_data)
    assert result is True

def test_disamb_and_fallback_trigger_none():
    rules = load_yaml('./tests/disambiguator/test_disambiguator9.yaml')
    disambiguator = Disambiguator(disamb_rule=rules['disambiguation_policy'],
                                fallback_rule=rules['fallback_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.51}, {"name": "intentB", "confidence": 0.25}]
    }
    result = disambiguator.should_fallback(parse_data) or disambiguator.should_disambiguate(parse_data)
    assert result is False