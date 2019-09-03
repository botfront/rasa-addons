from rasa_addons.core.policies.disambiguation import DisambiguationPolicy


def test_should_not_trigger():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger=0.30
    )

    intent_ranking = [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.2}]

    assert policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger) is False
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is False


def test_should_trigger_disamb_only():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger=0.30
    )

    intent_ranking = [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.4}]

    assert policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger) is True
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is False


def test_should_trigger_fallback_only():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger=0.30
    )

    intent_ranking = [{"name": "intentA", "confidence": 0.25}, {"name": "intentB", "confidence": 0.20}]

    assert policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger) is True
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is True

def test_localization_and_entity_substitution():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger=0.30,
        intent_mappings={
            "hola.test": { "en": "Testen {entity1}", "es": "Testes {entity1}", "fr": "Testfr {entity1}" },
            "intentA": { "en": "IntentAen", "es": "IntentAes", "fr": "IntentAfr" },
            "intentB": { "en": "IntentBen", "es": "IntentBes", "fr": "IntentBfr" },
            "deny_suggestions": { "en": "Something else", "es": "algo diferente", "fr": "autre chose" }
        },
        disambiguation_title={
            "en": "Do you mean...",
            "es": "Querías decir...",
            "fr": "Voulez-vous dire...",
        }
    )

    intent_ranking = [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.4}, {"name": "hola.test", "confidence": 0.4}]
    entities = [{"entity": "entity1", "value": "OH!"}]

    # English without entities
    assert policy.generate_disambiguation_message(intent_ranking, [], "en") == {
        "title": "Do you mean...",
        "buttons": [{
            "title": "IntentAen",
            "type": "postback",
            "payload": "/intentA"
        },
        {
            "title": "IntentBen",
            "type": "postback",
            "payload": "/intentB"
        },
        {
            "title": "Testen ",
            "type": "postback",
            "payload": "/hola.test"
        },
        {
            "title": "Something else",
            "type": "postback",
            "payload": "/deny_suggestions"
        }]
    }
    # French with entities and entity substitution
    assert policy.generate_disambiguation_message(intent_ranking, entities, "fr") == {
        "title": "Voulez-vous dire...",
        "buttons": [{
            "title": "IntentAfr",
            "type": "postback",
            "payload": "/intentA{\"entity1\": \"OH!\"}"
        },
        {
            "title": "IntentBfr",
            "type": "postback",
            "payload": "/intentB{\"entity1\": \"OH!\"}"
        },
        {
            "title": "Testfr OH!",
            "type": "postback",
            "payload": "/hola.test{\"entity1\": \"OH!\"}"
        },
        {
            "title": "autre chose",
            "type": "postback",
            "payload": "/deny_suggestions"
        }]
    }

def test_intent_exclusion():
    policy = DisambiguationPolicy(
        disambiguation_trigger='$0 < 2 * $1',
        fallback_trigger=0.30,
        excluded_intents=['^hola\..*'],
        intent_mappings={
            "hola.test": { "en": "Testen {entity1}", "es": "Testes {entity1}", "fr": "Testfr {entity1}" },
            "intentA": { "en": "IntentAen", "es": "IntentAes", "fr": "IntentAfr" },
            "intentB": { "en": "IntentBen", "es": "IntentBes", "fr": "IntentBfr" },
            "deny_suggestions": { "en": "Something else", "es": "algo diferente", "fr": "autre chose" }
        },
        disambiguation_title={
            "en": "Do you mean...",
            "es": "Querías decir...",
            "fr": "Voulez-vous dire...",
        }
    )

    intent_ranking = [{"name": "intentA", "confidence": 0.6}, {"name": "intentB", "confidence": 0.4}, {"name": "hola.test", "confidence": 0.4}]

    assert policy.generate_disambiguation_message(intent_ranking, [], "en") == {
        "title": "Do you mean...",
        "buttons": [{
            "title": "IntentAen",
            "type": "postback",
            "payload": "/intentA"
        },
        {
            "title": "IntentBen",
            "type": "postback",
            "payload": "/intentB"
        },
        {
            "title": "Something else",
            "type": "postback",
            "payload": "/deny_suggestions"
        }]
    }
