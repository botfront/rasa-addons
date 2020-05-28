from rasa_addons.core.policies.disambiguation import BotfrontDisambiguationPolicy


def test_should_not_trigger():
    policy = BotfrontDisambiguationPolicy(
        disambiguation_trigger="$0 < 2 * $1", fallback_trigger=0.30
    )

    intent_ranking = [
        {"name": "intentA", "confidence": 0.6},
        {"name": "intentB", "confidence": 0.2},
    ]

    assert (
        policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger)
        is False
    )
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is False


def test_should_trigger_disamb_only():
    policy = BotfrontDisambiguationPolicy(
        disambiguation_trigger="$0 < 2 * $1", fallback_trigger=0.30
    )

    intent_ranking = [
        {"name": "intentA", "confidence": 0.6},
        {"name": "intentB", "confidence": 0.4},
    ]

    assert (
        policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger)
        is True
    )
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is False


def test_should_trigger_fallback_only():
    policy = BotfrontDisambiguationPolicy(
        disambiguation_trigger="$0 < 2 * $1", fallback_trigger=0.30
    )

    intent_ranking = [
        {"name": "intentA", "confidence": 0.25},
        {"name": "intentB", "confidence": 0.20},
    ]

    assert (
        policy._should_disambiguate(intent_ranking, policy.disambiguation_trigger)
        is True
    )
    assert policy._should_fallback(intent_ranking, policy.fallback_trigger) is True


def test_localization_and_entity_substitution():
    policy = BotfrontDisambiguationPolicy(
        disambiguation_trigger="$0 < 2 * $1",
        fallback_trigger=0.30,
        n_suggestions=3,
    )

    intent_ranking = [
        {"name": "intentA", "confidence": 0.6, "canonical": "intent <A>"},
        {"name": "intentB", "confidence": 0.4, "canonical": "intent <B>"},
        {"name": "hola.test", "confidence": 0.4, "canonical": "Hola, test!"},
    ]
    entities = [{"entity": "entity1", "value": "OH!"}]

    assert policy.generate_disambiguation_message(intent_ranking, entities) == {
        "template": "utter_disambiguation",
        "quick_replies": [
            {"title": "intent <A>", "type": "postback", "payload": "/intentA{\"entity1\": \"OH!\"}"},
            {"title": "intent <B>", "type": "postback", "payload": "/intentB{\"entity1\": \"OH!\"}"},
            {"title": "Hola, test!", "type": "postback", "payload": "/hola.test{\"entity1\": \"OH!\"}"},
        ],
    }


def test_intent_exclusion():
    policy = BotfrontDisambiguationPolicy(
        disambiguation_trigger="$0 < 2 * $1",
        fallback_trigger=0.30,
        n_suggestions=3,
        excluded_intents=["^hola\..*"],
    )

    intent_ranking = [
        {"name": "intentA", "confidence": 0.6, "canonical": "intent <A>"},
        {"name": "intentB", "confidence": 0.4, "canonical": "intent <B>"},
        {"name": "hola.test", "confidence": 0.4, "canonical": "Hola, test!"},
    ]

    assert policy.generate_disambiguation_message(intent_ranking, []) == {
        "template": "utter_disambiguation",
        "quick_replies": [
            {"title": "intent <A>", "type": "postback", "payload": "/intentA"},
            {"title": "intent <B>", "type": "postback", "payload": "/intentB"},
        ],
    }
