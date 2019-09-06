from rasa.core.events import (
    UserUtteranceReverted,
    UserUttered,
    ActionExecuted,
    Event,
    SlotSet,
)
from rasa.core.actions.action import Action, ActionUtterTemplate, create_bot_utterance

from typing import Any, List, Text, Dict, Optional
import logging
import copy

from requests.auth import HTTPBasicAuth

logging.basicConfig(level="WARN")
logger = logging.getLogger()

class ActionBotfrontDisambiguation(Action):
    def name(self):
        return "action_botfront_disambiguation"

    async def run(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        message = None
        for event in list(tracker.events)[::-1]:
            logger.debug(event)
            if isinstance(event, SlotSet) and event.key == "disambiguation_message":
                message = event.value
                break
        if message:
            return [create_bot_utterance({ "text": message["title"], "buttons": message["buttons"] })]
        else:
            return []

class ActionBotfrontDisambiguationFollowup(Action):
    def name(self) -> Text:
        return "action_botfront_disambiguation_followup"

    async def run(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:

        revert_events = [
            UserUtteranceReverted(),
            UserUtteranceReverted(),
            ActionExecuted(action_name="action_listen"),
        ]

        last_user_event = None
        for event in list(tracker.events)[::-1]:
            if isinstance(event, UserUttered):
                last_user_event = copy.deepcopy(event)
                last_user_event.parse_data["intent"]["confidence"] = 1.0
                break
        if last_user_event:
            revert_events += [last_user_event]

        return revert_events

class ActionBotfrontFallback(ActionUtterTemplate):
    def name(self) -> Text:
        return "action_botfront_fallback"

    def __init__(self):
        super(ActionBotfrontFallback, self).__init__("utter_fallback", silent_fail=True)

    async def run(self, output_channel, nlg, tracker, domain):

        evts = await super(ActionBotfrontFallback, self).run(
            output_channel, nlg, tracker, domain
        )
        if (len(tracker.events) >= 4 and
        isinstance(tracker.events[-4], ActionExecuted) and
        tracker.events[-4].action_name ==
        "action_botfront_disambiguation"):
            return evts + [UserUtteranceReverted(), UserUtteranceReverted()]
        else:
            return evts + [UserUtteranceReverted()]

