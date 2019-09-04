from rasa_sdk import Action
from rasa_sdk.events import SlotSet, ReminderScheduled, UserUtteranceReverted, ActionExecuted, UserUttered

from typing import Any, List, Text, Dict, Optional
import logging
import json
import copy
import re

from requests.auth import HTTPBasicAuth

logging.basicConfig(level="WARN")
logger = logging.getLogger()

class ActionBotfrontDisambiguation(Action):
    def name(self):
        return "action_botfront_disambiguation"

    def run(self,
            dispatcher: "CollectingDispatcher",
            tracker: "Tracker",
            domain: Dict[Text, Any]
            ) -> List["Event"]:
        message = None
        for event in tracker.events[::-1]:
            if event.get("name", None) == "disambiguation_message":
                message = event["value"]
                break
        if message:
            dispatcher.utter_button_message(message["title"], buttons=message["buttons"])

        return []

class ActionBotfrontDisambiguationFollowup(Action):
    def name(self) -> Text:
        return "action_botfront_disambiguation_followup"

    def run(self,
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: Dict[Text, Any]
    ) -> List["Event"]:

        revert_events = [
            UserUtteranceReverted(),
            UserUtteranceReverted(),
            ActionExecuted(action_name="action_listen"),
        ]

        last_user_event = None
        for event in tracker.events[::-1]:
            if event["event"] == "user":
                last_user_event = copy.deepcopy(event)
                last_user_event["parse_data"]["intent"]["confidence"] = 1.0
                break
        if last_user_event:
            revert_events += [last_user_event]

        return revert_events

class ActionBotfrontFallback(Action):
    def name(self) -> Text:
        return "action_botfront_fallback"

    def run(self,
        dispatcher: "CollectingDispatcher",
        tracker: "Tracker",
        domain: Dict[Text, Any]
    ) -> List["Event"]:
        dispatcher.utter_template("utter_fallback", tracker)
        if (len(tracker.events) >= 4 and
        tracker.events[-4].get("name") ==
        "action_botfront_disambiguation"):
            return [UserUtteranceReverted(), UserUtteranceReverted()]
        else:
            return [UserUtteranceReverted()]
