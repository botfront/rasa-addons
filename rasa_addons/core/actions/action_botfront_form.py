import logging
import functools
from typing import Dict, Text, Any, List, Union, Optional, Tuple
from rasa_addons.core.actions.slot_rule_validator import validate_with_rule
from rasa_addons.core.actions.submit_form_to_botfront import submit_form_to_botfront

from rasa.core.actions.action import (
    Action,
    ActionExecutionRejection,
    create_bot_utterance,
)
from rasa.core.events import Event, Form, SlotSet
from rasa.core.constants import REQUESTED_SLOT

logger = logging.getLogger(__name__)

"""
    This is mostly a port of ActionForm from Rasa-SDK, modified
    to use a JSON API instead of a Python class-based one.
"""


class ActionBotfrontForm(Action):
    def __init__(self, name: Text):
        self.action_name = name
        self.form_spec = {}

    def name(self) -> Text:
        return self.action_name

    def __str__(self) -> Text:
        return f"FormAction('{self.name()}')"

    def required_slots(self, tracker):
        return [s.get("name") for s in self.form_spec.get("slots", [])]

    def get_field_for_slot(
        self, slot: Text, field: Text, default: Optional[Any] = None,
    ) -> Optional[List[Dict[Text, Any]]]:
        for s in self.form_spec.get("slots", []):
            if s.get("name") == slot:
                return s.get(field, default)
        return None

    async def run(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        # attempt retrieving spec
        if not len(self.form_spec):
            for form in tracker.slots.get("bf_forms", {}).initial_value:
                if form.get("name") == self.name():
                    self.form_spec = form
            if not len(self.form_spec):
                logger.debug(
                    f"Could not retrieve form '{tracker.active_form}', there is something wrong with your domain."
                )
                return [Form(None)]

        # activate the form
        events = await self._activate_if_required(output_channel, nlg, tracker, domain)
        # validate user input
        events.extend(
            await self._validate_if_required(output_channel, nlg, tracker, domain)
        )
        # check that the form wasn't deactivated in validation
        if Form(None) not in events:

            # create temp tracker with populated slots from `validate` method
            temp_tracker = tracker.copy()
            for e in events:
                if isinstance(e, SlotSet):
                    temp_tracker.slots[e.key].value = e.value

            next_slot_events = await self.request_next_slot(
                output_channel, nlg, temp_tracker, domain
            )

            if next_slot_events is not None:
                # request next slot
                events.extend(next_slot_events)
            else:
                # there is nothing more to request, so we can submit
                self._log_form_slots(temp_tracker)
                logger.debug(f"Submitting the form '{self.name()}'")
                events.extend(await self.submit(output_channel, nlg, temp_tracker, domain))
                # deactivate the form after submission
                events.extend(self.deactivate())

        return events

    def deactivate(self) -> List[Event]:
        logger.debug(f"Deactivating the form '{self.name()}'")
        return [Form(None), SlotSet(REQUESTED_SLOT, None)]

    async def submit(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        events = []
        utter_on_submit = self.form_spec.get("utter_on_submit", False)
        collect_in_botfront = self.form_spec.get("collect_in_botfront", False)
        if utter_on_submit:
            template = await nlg.generate(
                f"utter_submit_{self.name()}", tracker, output_channel.name(),
            )
            events += [create_bot_utterance(template)]
        if collect_in_botfront: submit_form_to_botfront(tracker)
        return events

    @staticmethod
    def pointwise_entity_mapping(mapping):
        """Allows entity arrays to be used with 'from_entity' type"""
        mapping_type, entity = mapping.get("type"), mapping.get("entity")
        if mapping_type == "from_entity":
            if type(entity) != list:
                entity = [entity]
            return [{**mapping, "entity": e} for e in entity]
        return [mapping]

    def get_mappings_for_slot(self, slot_to_fill: Text) -> List[Dict[Text, Any]]:
        slot_mappings = self.get_field_for_slot(
            slot_to_fill, "filling", [{"type": "from_entity", "entity": slot_to_fill,}]
        )
        return functools.reduce(
            lambda acc, curr: acc + self.pointwise_entity_mapping(curr),
            slot_mappings,
            [],
        )

    @staticmethod
    def intent_is_desired(
        requested_slot_mapping: Dict[Text, Any], tracker: "DialogueStateTracker",
    ) -> bool:
        mapping_intents = requested_slot_mapping.get("intent", [])
        mapping_not_intents = requested_slot_mapping.get("not_intent", [])
        intent = (
            tracker.latest_message.as_dict()
            .get("parse_data", {})
            .get("intent", {})
            .get("name")
        )

        intent_not_blacklisted = (
            not mapping_intents and intent not in mapping_not_intents
        )

        return intent_not_blacklisted or intent in mapping_intents

    def entity_is_desired(
        self,
        requested_slot_mapping: Dict[Text, Any],
        slot: Text,
        tracker: "DialogueStateTracker",
    ) -> bool:
        # slot name is equal to the entity type
        slot_equals_entity = slot == requested_slot_mapping.get("entity")

        # use the custom slot mapping 'from_entity' defined by the user to check
        # whether we can fill a slot with an entity
        matching_values = self.get_entity_value(
            requested_slot_mapping.get("entity"),
            tracker,
            requested_slot_mapping.get("role"),
            requested_slot_mapping.get("group"),
        )
        slot_fulfils_entity_mapping = matching_values is not None

        return slot_equals_entity or slot_fulfils_entity_mapping

    @staticmethod
    def get_entity_value(
        name: Text,
        tracker: "DialogueStateTracker",
        role: Optional[Text] = None,
        group: Optional[Text] = None,
    ) -> Any:
        # list is used to cover the case of list slot type
        value = list(
            tracker.get_latest_entity_values(name, entity_group=group, entity_role=role)
        )
        if len(value) == 0:
            value = None
        elif len(value) == 1:
            value = value[0]
        return value

    # noinspection PyUnusedLocal
    def extract_other_slots(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> Dict[Text, Any]:
        slot_to_fill = tracker.get_slot(REQUESTED_SLOT)

        slot_values = {}
        for slot in self.required_slots(tracker):
            # look for other slots
            if slot != slot_to_fill:
                # list is used to cover the case of list slot type
                other_slot_mappings = self.get_mappings_for_slot(slot)

                for other_slot_mapping in other_slot_mappings:
                    # check whether the slot should be filled by an entity in the input
                    should_fill_entity_slot = (
                        other_slot_mapping["type"] == "from_entity"
                        and self.intent_is_desired(other_slot_mapping, tracker)
                        and self.entity_is_desired(other_slot_mapping, slot, tracker)
                    )
                    # check whether the slot should be
                    # filled from trigger intent mapping
                    should_fill_trigger_slot = (
                        tracker.active_form.get("name") != self.name()
                        and other_slot_mapping["type"] == "from_trigger_intent"
                        and self.intent_is_desired(other_slot_mapping, tracker)
                    )
                    if should_fill_entity_slot:
                        value = self.get_entity_value(
                            other_slot_mapping["entity"],
                            tracker,
                            other_slot_mapping.get("role"),
                            other_slot_mapping.get("group"),
                        )
                    elif should_fill_trigger_slot:
                        value = other_slot_mapping.get("value")
                    else:
                        value = None

                    if value is not None:
                        logger.debug(f"Extracted '{value}' for extra slot '{slot}'.")
                        slot_values[slot] = value
                        # this slot is done, check  next
                        break

        return slot_values

    # noinspection PyUnusedLocal
    def extract_requested_slot(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> Dict[Text, Any]:
        """Extract the value of requested slot from a user input
            else return None
        """
        slot_to_fill = tracker.get_slot(REQUESTED_SLOT)
        logger.debug(f"Trying to extract requested slot '{slot_to_fill}' ...")

        # get mapping for requested slot
        requested_slot_mappings = self.get_mappings_for_slot(slot_to_fill)

        for requested_slot_mapping in requested_slot_mappings:
            logger.debug(f"Got mapping '{requested_slot_mapping}'")

            if self.intent_is_desired(requested_slot_mapping, tracker):
                mapping_type = requested_slot_mapping["type"]

                if mapping_type == "from_entity":
                    value = self.get_entity_value(
                        requested_slot_mapping.get("entity"),
                        tracker,
                        requested_slot_mapping.get("role"),
                        requested_slot_mapping.get("group"),
                    )
                elif mapping_type == "from_intent":
                    value = requested_slot_mapping.get("value")
                elif mapping_type == "from_trigger_intent":
                    # from_trigger_intent is only used on form activation
                    continue
                elif mapping_type == "from_text":
                    value = tracker.latest_message.as_dict().get("text")
                else:
                    raise ValueError("Provided slot mapping type is not supported")

                if value is not None:
                    logger.debug(
                        f"Successfully extracted '{value}' for requested slot '{slot_to_fill}'"
                    )
                    return {slot_to_fill: value}

        logger.debug(f"Failed to extract requested slot '{slot_to_fill}'")
        return {}

    async def utter_post_validation(
        self,
        slot,
        value,
        valid: bool,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        if (
            valid
            and self.get_field_for_slot(slot, "utter_on_new_valid_slot", False) is False
        ):
            return []
        valid = "valid" if valid else "invalid"

        # so utter_(in)valid_slot supports {slot} template replacements
        temp_tracker = tracker.copy()
        temp_tracker.slots[slot].value = value
        template = await nlg.generate(
            f"utter_{valid}_{slot}", temp_tracker, output_channel.name(),
        )
        return [create_bot_utterance(template)]

    async def validate_slots(
        self,
        slot_dict: Dict[Text, Any],
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        events = []
        for slot, value in list(slot_dict.items()):
            validation_rule = self.get_field_for_slot(slot, "validation")
            validated = validate_with_rule(value, validation_rule)

            events += [SlotSet(slot, value if validated else None)]

            events += await self.utter_post_validation(
                slot, value, validated, output_channel, nlg, tracker, domain
            )

        return events

    async def validate(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:

        # extract other slots that were not requested
        # but set by corresponding entity or trigger intent mapping
        slot_values = self.extract_other_slots(output_channel, nlg, tracker, domain)

        # extract requested slot
        slot_to_fill = tracker.get_slot(REQUESTED_SLOT)
        if slot_to_fill:
            slot_values.update(
                self.extract_requested_slot(output_channel, nlg, tracker, domain)
            )

            if not slot_values:
                # reject to execute the form action
                # if some slot was requested but nothing was extracted
                # it will allow other policies to predict another action
                raise ActionExecutionRejection(
                    self.name(),
                    f"Failed to extract slot {slot_to_fill} with action {self.name()}",
                )
        logger.debug(f"Validating extracted slots: {slot_values}")
        return await self.validate_slots(
            slot_values, output_channel, nlg, tracker, domain
        )

    # noinspection PyUnusedLocal
    async def request_next_slot(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> Optional[List[Event]]:
        """Request the next slot and utter template if needed,
            else return None"""

        for slot in self.required_slots(tracker):
            if self._should_request_slot(tracker, slot):

                template = await nlg.generate(
                    f"utter_ask_{slot}", tracker, output_channel.name(),
                )
                logger.debug(f"Request next slot '{slot}'")
                return [create_bot_utterance(template), SlotSet(REQUESTED_SLOT, slot)]

        # no more required slots to fill
        return None

    def _log_form_slots(self, tracker) -> None:
        """Logs the values of all required slots before submitting the form."""
        slot_values = "\n".join(
            [
                f"\t{slot}: {tracker.get_slot(slot)}"
                for slot in self.required_slots(tracker)
            ]
        )
        logger.debug(
            f"No slots left to request, all required slots are filled:\n{slot_values}"
        )

    async def _activate_if_required(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        if tracker.active_form.get("name") is not None:
            logger.debug(f"The form '{tracker.active_form}' is active")
        else:
            logger.debug("There is no active form")

        if tracker.active_form.get("name") == self.name():
            return []
        else:
            logger.debug(f"Activated the form '{self.name()}'")
            events = [Form(self.name())]

            # collect values of required slots filled before activation
            prefilled_slots = {}

            for slot_name in self.required_slots(tracker):
                if not self._should_request_slot(tracker, slot_name):
                    prefilled_slots[slot_name] = tracker.get_slot(slot_name)

            if prefilled_slots:
                logger.debug(f"Validating pre-filled required slots: {prefilled_slots}")
                events.extend(
                    await self.validate_slots(
                        prefilled_slots, output_channel, nlg, tracker, domain
                    )
                )
            else:
                logger.debug("No pre-filled required slots to validate.")

            return events

    async def _validate_if_required(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        if tracker.latest_action_name == "action_listen" and tracker.active_form.get(
            "validate", True
        ):
            logger.debug(f"Validating user input '{tracker.latest_message}'")
            return await self.validate(output_channel, nlg, tracker, domain)
        else:
            logger.debug("Skipping validation")
            return []

    @staticmethod
    def _should_request_slot(tracker: "DialogueStateTracker", slot_name: Text) -> bool:
        return tracker.get_slot(slot_name) is None
