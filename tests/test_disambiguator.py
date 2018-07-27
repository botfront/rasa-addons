import os
import pytest
from rasa_addons.superagent.dismabiguator import Disambiguator, ActionDisambiguate
from rasa_addons.superagent.rules import Rules
from rasa_addons.utils import load_yaml
from schema import SchemaError
from rasa_core.dispatcher import Dispatcher

ROOT_PATH = os.path.join(os.getcwd(), 'tests')


class TestDispatcher(object):

    def retrieve_template(self, template_name, filled_slots=None, **kwargs):
        """Retrieve a named template from the domain."""
        return {"text": template_name}


def test_dismabiguator_trigger_wrong_format():
    with pytest.raises(SchemaError) as e:
        Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator3.yaml')['disambiguation_policy'])


def test_dismabiguator_trigger1():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.5}]
    }
    result = disambiguator.should_disambiguate(parse_data)
    assert result is True


def test_dismabiguator_trigger2():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]
    }
    result = disambiguator.should_disambiguate(parse_data)
    assert result is False


def test_buttons_with_fallback():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator2.yaml')['disambiguation_policy'])

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

    dispatcher = TestDispatcher()
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.rule,
                                                         disambiguator.get_payloads(parse_data),
                                                         disambiguator.get_intent_names(parse_data)) == expected


def test_buttons_without_fallback():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

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

    dispatcher = TestDispatcher()
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.rule,
                                                         disambiguator.get_payloads(parse_data),
                                                         disambiguator.get_intent_names(parse_data)) == expected


def test_with_entities():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

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
    dispatcher = TestDispatcher()
    assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.rule,
                                                         disambiguator.get_payloads(parse_data),
                                                         disambiguator.get_intent_names(parse_data)) == expected

def test_does_not_disambiguate_when_data_is_missing_in_parse_data():
    disambiguator = Disambiguator(load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])

    parse_data = {

    }
    assert disambiguator.should_disambiguate(parse_data) is False

