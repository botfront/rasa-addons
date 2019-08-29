from rasa_addons.core.policies.disambiguation import DisambiguationPolicy


def test_should_not_trigger():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger='$0 <= 0.30'
    )

    parse_data = {
            "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}],
            "entities": [{"entity": "entity1", "value": "value1"}]
        }
    assert policy.is_triggered(parse_data, policy.disambiguation_trigger) is False
    assert policy.is_triggered(parse_data, policy.fallback_trigger) is False
    assert policy.should_fallback(parse_data, 'action_listen') is False
    assert policy.should_disambiguate(parse_data, 'action_listen') is False


def test_should_trigger_disamb_only():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger='$0 <= 0.30'
    )

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.4}],
        "entities": [{"entity": "entity1", "value": "value1"}]
    }
    assert policy.is_triggered(parse_data, policy.disambiguation_trigger) is True
    assert policy.is_triggered(parse_data, policy.fallback_trigger) is False
    assert policy.should_disambiguate(parse_data, 'action_listen') is True
    assert policy.should_fallback(parse_data, 'action_listen') is False


def test_should_trigger_fallback_only():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger='$0 <= 0.30'
    )

    parse_data = {
        "intent_ranking": [{"name": "intentA", "confidence": 0.25}, {"name": "intentB", "confidence": 0.20}],
        "entities": [{"entity": "entity1", "value": "value1"}]
    }
    assert policy.is_triggered(parse_data, policy.disambiguation_trigger) is True
    assert policy.is_triggered(parse_data, policy.fallback_trigger) is True
    assert policy.should_fallback(parse_data, 'action_listen') is True
    assert policy.should_disambiguate(parse_data, 'action_listen') is False




# def test_disamb_with_entities():
#     disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])
#
#     parse_data = {
#         "intent_ranking": [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}],
#         "entities": [{"entity": "entity1", "value": "value1"}]
#     }
#
#     expected = {
#         "text": "utter_disamb_text",
#         "buttons": [{
#             "title": "utter_disamb_intentA",
#             "payload": "/intentA{\"entity1\": \"value1\"}"
#         }, {
#             "title": "utter_disamb_intentB",
#             "payload": "/intentB{\"entity1\": \"value1\"}"
#         }]
#     }
#     dispatcher = StubDispatcher()
#     intents = disambiguator.get_intent_names(parse_data)
#     assert ActionDisambiguate.get_disambiguation_message(dispatcher, disambiguator.disamb_rule,
#                                                          disambiguator.get_payloads(parse_data, intents),
#                                                          intents,
#                                                          tracker) == expected


# def test_disamb_does_not_trigger_when_data_is_missing_in_parse_data():
#     disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])
#
#     parse_data = {
#
#     }
#     assert disambiguator.should_disambiguate(parse_data) is False


# def test_disamb_does_not_trigger_when_intent_is_null():
#     disambiguator = Disambiguator(disamb_rule=load_yaml('./tests/disambiguator/test_disambiguator4.yaml')['disambiguation_policy'])
#
#     parse_data = {
#         "intent": {
#             "name": None,
#             "confidence": 0.0
#         },
#         "entities": [],
#         "intent_ranking": []
#     }
#
#     assert disambiguator.should_disambiguate(parse_data) is False
