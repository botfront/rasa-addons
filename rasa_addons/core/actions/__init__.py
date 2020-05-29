from rasa_addons.core.actions.action_botfront_mapping import ActionBotfrontMapping
from rasa_addons.core.actions.action_botfront_disambiguation import ActionBotfrontDisambiguation, ActionBotfrontDisambiguationFollowup, ActionBotfrontFallback
from rasa_addons.core.actions.action_botfront_form import ActionBotfrontForm

from typing import List, Text, Optional, Dict, Any

def actions() -> List["Action"]:
    return [
        ActionBotfrontMapping(),
        ActionBotfrontDisambiguation(),
        ActionBotfrontDisambiguationFollowup(),
        ActionBotfrontFallback()
    ]

actions_bf = {a.name(): a for a in actions()}

def generate_bf_form_action(name):
    return ActionBotfrontForm(name)