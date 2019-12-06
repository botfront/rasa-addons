from rasa.core.events import Event
from rasa.core.actions.action import Action, ActionUtterTemplate, create_bot_utterance

from typing import Any, List, Text, Dict, Optional
import logging
import copy

from requests.auth import HTTPBasicAuth

logging.basicConfig(level="WARN")
logger = logging.getLogger()

class ActionBotfrontMapping(Action):
    def name(self):
        return 'action_botfront_mapping'

    async def run(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
    ) -> List[Event]:
        """Append 'utter_' to intent name and generates from that template"""

        events = []
        response_name = 'utter_' + tracker.latest_message.intent["name"]
        events += [create_bot_utterance(m) for m in await nlg.generate(response_name, tracker, output_channel.name(),
                   language=tracker.latest_message.metadata["language"])]

        return events
