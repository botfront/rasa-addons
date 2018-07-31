import yaml
from rasa_addons.superagent.input_validator import InputValidator
from rasa_addons.superagent.rules import Rules

VALIDATOR_RULES_YAML = './tests/test_rules.yaml'


def test_validator_intent_and_entity_ok():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': 'garantie'},
        'entities': [{'entity': 'product_type'}]
    }
    assert validator._get_error(parse_data, previous) is None


def test_validator_dummy_valid():

    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "not_in_file"
    parse_data = {
        'intent': {'name': 'affirm'},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) is None


def test_validator_intent_no_entity():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': 'cancel'},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) is None


def test_validator_entity_not_in_expected():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])

    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': 'cancel'},
        'entities': [{'entity': 'product_type'}]
    }
    assert validator._get_error(parse_data, previous) is None


def test_validator_regex():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])

    previous = "utter_garantie_confirm_particulier"
    parse_data = {
        'intent': {'name': 'cancel'},
        'entities': [{'entity': 'product_type'}]
    }
    # having an entity in parse_data that is not expected is ok
    assert validator._get_error(parse_data, previous) is None

    previous = "utter_garantie_confirm_particulier"
    parse_data = {
        'intent': {'name': 'cancel'},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) is None

    previous = "utter_garantie_confirm_particulier"
    parse_data = {
        'intent': {'name': 'lakjshdflkjashdf'},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) == 'utter_general_validation_affirm_deny'


def test_validator_intent_ok_entity_missing():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': 'garantie'},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) == 'utter_general_validation_options'

def test_validator_intent_empty():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': ''},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) == 'utter_general_validation_options'

def test_validator_intent_none():
    validator = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['input_validation'])
    previous = "utter_garantie_type_bien"
    parse_data = {
        'intent': {'name': None},
        'entities': []
    }
    assert validator._get_error(parse_data, previous) == 'utter_general_validation_options'

def test_swap_intent_none():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent swapped
    parse_data = {"intent": {"name": None, "confidence": 0.0}}
    Rules._swap_intent(parse_data,  "utter_something", swap_rules.rules[0])
    assert parse_data["intent"]["name"] is None


def test_swap_intent_empty():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent swapped
    parse_data = {"intent": {"name": "", "confidence": 0.0}}
    Rules._swap_intent(parse_data,  "utter_something", swap_rules.rules[0])
    assert parse_data["intent"]["name"] == ""


def test_swap_intent_after1():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent swapped
    parse_data = {"intent": {"name": "whatever", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  "utter_something", swap_rules.rules[0])
    assert parse_data["intent"]["name"] == "intent_something"


def test_swap_intent_after2():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent is not swapped when in unless list
    parse_data = {"intent": {"name": "chitchat.this_is_frustrating", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  "utter_something", swap_rules.rules[0])
    assert parse_data["intent"]["name"] == "chitchat.this_is_frustrating"


def test_swap_intent_after3():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent not swapped after another action than the one specified in the rule
    parse_data = {"intent": {"name": "whatever", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  "utter_no", swap_rules.rules[0])
    assert parse_data["intent"]["name"] == "whatever"


def test_swap_intent_with1():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent swapped
    parse_data = {"intent": {"name": "chitchat.i_am_angry", "confidence": 1.0}}
    Rules._swap_intent(parse_data, None, swap_rules.rules[1])
    assert parse_data["intent"]["name"] == "request.handover"


def test_swap_intent_with2():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent not swapped after another action than the one specified in the rule
    parse_data = {"intent": {"name": "whatever", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  None, swap_rules.rules[1])
    assert parse_data["intent"]["name"] == "whatever"


def test_swap_intent_with3():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # make sure intent is swapped and entity is added
    parse_data = {"intent": {"name": "chitchat.bye", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  None, swap_rules.rules[2])
    assert parse_data["intent"]["name"] == "chitchat"
    assert parse_data["entities"][0]["entity"] == "intent"
    assert parse_data["entities"][0]["value"] == "chitchat.bye"


def test_swap_intent_with4():
    swap_rules = InputValidator(InputValidator._load_yaml(VALIDATOR_RULES_YAML)['intent_substitution'])
    # just checking regex is ok
    parse_data = {"intent": {"name": "chitchat.this_is_frustrating", "confidence": 1.0}}
    Rules._swap_intent(parse_data,  None, swap_rules.rules[2])
    assert parse_data["intent"]["name"] == "chitchat.this_is_frustrating"
