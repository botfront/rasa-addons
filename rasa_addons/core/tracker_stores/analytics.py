import logging
from rasa.core.events import UserUttered
from rasa_addons.core.tracker_stores.botfront import BotfrontTrackerStore
from rasa_addons.core.tracker_stores.askhub import AskHubAnalytics
from rasa_addons.core.tracker_stores.chatbase import ChatbaseAnalytics
from rasa_addons.utils import get_latest_parse_data_language

logger = logging.getLogger(__name__)


class AnalyticsTrackerStore(BotfrontTrackerStore):
    def __init__(self, domain, url, **kwargs):
        super(AnalyticsTrackerStore, self).__init__(domain, url, **kwargs)
        self.chatbase_api_key = kwargs.get('chatbase_api_key')
        self.chatbase_version = str(kwargs.get('chatbase_version', 0))
        self.askhub_api_key = kwargs.get('askhub_api_key')
        self.askhub_response_format = kwargs.get('askhub_response_format', 'botfront')
        self.latest_response_name = kwargs.get('latest_response_name', 'latest_response_name')
        self.special_action_responses = kwargs.get('special_actions_responses', [])

    def save(self, tracker):
        all_events = super(AnalyticsTrackerStore, self).save(tracker)
        platform = self.get_latest_input_channel(tracker)
        if self.is_end_of_turn(all_events[-1]):
            latest_turn = self.get_latest_turn(all_events)
            if latest_turn:
                if self.askhub_api_key:
                    AskHubAnalytics().save(latest_turn, tracker, all_events, platform, self)
                if self.chatbase_api_key:
                    ChatbaseAnalytics().save(latest_turn, tracker, all_events, platform, self)

    def get_latest_turn(self, all_events):
        events = reversed(all_events)
        latest_turn = {
            'bot_events': [],
            'response_names': [],
        }
        try:
            while True:
                event = next(events)
                # print (evt)
                if event['event'] == 'bot':
                    latest_turn['bot_events'].insert(0, event)
                # Get response name from FAQ action
                if event['event'] == 'slot' and event['name'] == 'latest_response_name':
                    latest_turn['response_names'].insert(0, event['value'])
                # Get response name from utter action
                if event['event'] == 'action' and event['name'].startswith('utter'):
                    latest_turn['response_names'].insert(0, event['name'])
                # Get special action response names
                special_actions = list(map(lambda a: a['action_name'], self.special_action_responses))
                if event['event'] == 'action' and event['name'] in special_actions:
                    response_name = next((x for x in self.special_action_responses
                                        if x['action_name'] == event['name']))['response_name']
                    latest_turn['response_names'].insert(0, response_name)
                if event['event'] == 'user':
                    latest_turn['user_event'] = event
                    break

            latest_turn['parse_data'] = AnalyticsTrackerStore.get_parse_data(latest_turn)
            latest_turn['language'] = get_latest_parse_data_language(all_events)
            intent = AnalyticsTrackerStore.get_latest_intent(latest_turn['parse_data'])
            if intent:
                latest_turn['intent'] = intent
        except StopIteration:
            return None
        return latest_turn

    def is_latest_bot_response(self, event):
        return event['event'] == 'slot' and event['name'] == self.latest_response_name

    def is_fallback(self, event):
        return event['event'] == 'action' and event['name'] == self.fallback_action_name

    @staticmethod
    def is_end_of_turn(event):
        return event['event'] == 'action' and event['name'] == 'action_listen'

    @staticmethod
    def get_parse_data(latest_turn):
        parse_data = latest_turn['user_event']['parse_data']
        if 'original_data' in parse_data:
            parse_data = parse_data['original_data']
        return parse_data

    @staticmethod
    def get_latest_intent(parse_data):
        return parse_data['intent']['name'] if 'intent' in parse_data and 'name' in parse_data['intent'] else None

    @staticmethod
    def get_latest_input_channel(tracker):
        for event in reversed(tracker.events):
            if isinstance(event, UserUttered) and event.input_channel is not None:
                return event.input_channel
