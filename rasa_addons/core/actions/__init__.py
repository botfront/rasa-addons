from rasa_addons.core.actions.action_botfront_mapping import ActionBotfrontMapping
from rasa_addons.core.actions.action_botfront_disambiguation import ActionBotfrontDisambiguation, ActionBotfrontDisambiguationFollowup, ActionBotfrontFallback

from typing import List, Text, Optional, Dict, Any

def actions() -> List["Action"]:
    return [
        ActionBotfrontMapping(),
        ActionBotfrontDisambiguation(),
        ActionBotfrontDisambiguationFollowup(),
        ActionBotfrontFallback()
    ]

actions_bf = {a.name(): a for a in actions()}
