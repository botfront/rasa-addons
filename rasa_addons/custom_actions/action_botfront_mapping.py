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

class ActionBotfrontMapping(Action):

    def name(self):
        return 'action_botfront_mapping'

    def run(self, dispatcher, tracker, domain):

        events = []
        payload = {
            "nlu": {
                "intent": tracker.latest_message["intent"]["name"],
                "entities": tracker.latest_message["entities"]
                }
            }

        url = "{base_url}/project/{project_id}/response".format(
            base_url=os.environ.get('BF_URL'), project_id=os.environ.get("BF_PROJECT_ID"))
        try:
            response_sent = False
            result = requests.post(url, json=payload)

            if result.status_code == 200:
                response = result.json()
                response_name = response["key"]
                dispatcher.utter_template(response_name, tracker)
                response_sent = True

                events.append(SlotSet('latest_response_name', response_name))
                if 'follow_up' in response and response['follow_up'].get('action') :
                    if response['follow_up']['action'].startswith('utter'):
                        action = 'action_botfront_mapping_follow_up'
                        events.append(SlotSet('followup_response_name', response['follow_up']['action']))

                    # FollowUpAction produces random results, so we force a minimum delay for a reminder.
                    delay = max(2, int(response['follow_up']['delay']))
                    events.append(ReminderScheduled(
                        action, 
                        datetime.now() + timedelta(seconds=delay), 
                        kill_on_user_message=True))
               
            elif result.status_code == 404:
                logger.warning('Response not found for: {}'.format(str(payload)))
                events.append(SlotSet('latest_response_name', 'error_response_not_found'))
                if not response_sent:
                    dispatcher.utter_template("utter_fallback", tracker)
            else:
                logger.warning('Error {} with request: {}'.format(result.status_code, str(payload)))
                events.append(SlotSet('latest_response_name', 'error_unknown_error'))
                if not response_sent:
                    dispatcher.utter_template("utter_fallback", tracker)

        except StopIteration:
            logger.error('Error with request {}: {}'.format(str(payload), "No intent was passed as an entity"))
            events.append(SlotSet('latest_response_name', 'error_no_intent'))
            dispatcher.utter_template("utter_fallback", tracker)
        except Exception as e:
            logger.error('Error with request {}: {}'.format(str(payload), e))
            events.append(SlotSet('latest_response_name', 'error_unknown_error'))
            dispatcher.utter_template("utter_fallback", tracker)
        return events
