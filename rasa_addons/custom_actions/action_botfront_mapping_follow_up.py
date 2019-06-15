from rasa_sdk import Action
from rasa_sdk.events import SlotSet, ReminderScheduled

import time
from datetime import datetime, timedelta
import logging
import requests
import os
import copy
import re

from requests.auth import HTTPBasicAuth

logging.basicConfig(level="WARN")
logger = logging.getLogger()

class ActionBotfrontMappingFollowUp(Action):
    
    def name(self):
        return 'action_botfront_mapping_follow_up'
    
    def run(self, dispatcher, tracker, domain):
        action = tracker.get_slot('followup_response_name')
        if action:
            dispatcher.utter_template(action, tracker)
        return [
            SlotSet('followup_response_name', None),
            SlotSet('latest_response_name', action)
        ]