from rasa_addons.core.actions.action_botfront_form import ActionBotfrontForm
from rasa_addons.core.nlg.bftemplate import BotfrontTemplatedNaturalLanguageGenerator
from rasa.core.domain import Domain
from rasa.core.channels.channel import OutputChannel
from rasa.core.trackers import DialogueStateTracker
from rasa.core.events import (
    UserUtteranceReverted,
    UserUttered,
    ActionExecuted,
    Event,
    SlotSet,
    BotUttered,
)
from rasa.core.slots import Slot
import pytest

nlg = BotfrontTemplatedNaturalLanguageGenerator()
def new_form_and_tracker(form_spec, requested_slot):
    form = ActionBotfrontForm(form_spec.get("form_name"))
    tracker = DialogueStateTracker.from_dict(
        "default",
        [],
        [
            Slot(name=requested_slot),
            Slot(name="requested_slot", initial_value=requested_slot),
            Slot(
                name="bf_forms",
                initial_value=[form_spec]
            )
        ]
    )
    form.form_spec = form_spec # load spec manually
    return form, tracker

def test_extract_requested_slot_default():
    """Test default extraction of a slot value from entity with the same name
    """

    spec = {"name": "default_form"}

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(entities=[{"entity": "some_slot", "value": "some_value"}]))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {"some_slot": "some_value"}

def test_extract_requested_slot_from_entity_no_intent():
    """Test extraction of a slot value from entity with the different name
        and any intent
    """

    spec = {
        "name": "default_form",
        "slots": [{
            "name": "some_slot",
            "filling": [{
                "type": "from_entity",
                "entity": ["some_entity"]
            }]
        }]
    }

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(entities=[{"entity": "some_entity", "value": "some_value"}]))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {"some_slot": "some_value"}

def test_extract_requested_slot_from_entity_with_intent():
    """Test extraction of a slot value from entity with the different name
        and certain intent
    """

    spec = {
        "name": "default_form",
        "slots": [{
            "name": "some_slot",
            "filling": [{
                "type": "from_entity",
                "entity": ["some_entity"],
                "intent": ["some_intent"]
            }]
        }]
    }

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(
        intent={"name": "some_intent", "confidence": 1.0},
        entities=[{"entity": "some_entity", "value": "some_value"}]
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {"some_slot": "some_value"}

    tracker.update(UserUttered(
        intent={"name": "some_other_intent", "confidence": 1.0},
        entities=[{"entity": "some_entity", "value": "some_value"}]
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {}

def test_extract_requested_slot_from_intent():
    """Test extraction of a slot value from certain intent
    """

    spec = {
        "name": "default_form",
        "slots": [{
            "name": "some_slot",
            "filling": [{
                "type": "from_intent",
                "intent": ["some_intent"],
                "value": "some_value"
            }]
        }]
    }

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(
        intent={"name": "some_intent", "confidence": 1.0}
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {"some_slot": "some_value"}

    tracker.update(UserUttered(
        intent={"name": "some_other_intent", "confidence": 1.0}
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {}

def test_extract_requested_slot_from_text_with_not_intent():
    """Test extraction of a slot value from text with certain intent
    """

    spec = {
        "name": "default_form",
        "slots": [{
            "name": "some_slot",
            "filling": [{
                "type": "from_text",
                "not_intent": ["some_intent"],
            }]
        }]
    }

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(
        intent={"name": "some_intent", "confidence": 1.0},
        text="some_text"
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {}

    tracker.update(UserUttered(
        intent={"name": "some_other_intent", "confidence": 1.0},
        text="some_text"
    ))

    slot_values = form.extract_requested_slot(OutputChannel(), nlg, tracker, Domain.empty())
    assert slot_values == {"some_slot": "some_text"}

@pytest.mark.parametrize(
    "operator, value, comparatum, result", [
        ("is_in", "hey", ["hey", "ho", "fee"], True),
        ("is_exactly", "aheya", "hey", False),
        ("contains", "aheya", "hey", True),
        ("ends_with", "hey", 5, None),
        ("eq", "5", 5, True),
        ("eq", "5", "a", None),
        ("gt", 4, 5, False),
        ("shorter_or_equal", "hey", "3", True),
        ("shorter_or_equal", "heya", "3", False),
        ("shorter_or_equal", "heya", "a", None),
        ("email", "joe@hotmail.com", None, True),
        ("email", "joe@ hotmail.com", None, False),
        ("word", "joe is", None, False),
        ("word", "joe", None, True),
    ],
)
async def test_validation(value, operator, comparatum, result, caplog):
    spec = {
        "name": "default_form",
        "slots": [{
            "name": "some_slot",
            "validation": {
                "operator": operator,
                "comparatum": comparatum,
            }
        }]
    }

    form, tracker = new_form_and_tracker(spec, "some_slot")
    tracker.update(UserUttered(entities=[{"entity": "some_slot", "value": value}]))

    events = await form.validate(OutputChannel(), nlg, tracker, Domain.empty())

    if result is True:
        assert len(events) == 1
        assert isinstance(events[0], SlotSet) and events[0].value == value
    else:
        assert len(events) == 2
        assert isinstance(events[0], SlotSet) and events[0].value == None
        assert isinstance(events[1], BotUttered) and events[1].text == "utter_invalid_some_slot"
        if result is None:
            assert f"Validation operator '{operator}' requires" in caplog.messages[0]
