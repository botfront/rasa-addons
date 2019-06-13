import logging
import requests
from requests_futures.sessions import FuturesSession
logger = logging.getLogger(__name__)


class ChatbaseAnalytics(object):

    def save(self, latest_turn, tracker, all_events, platform, tracker_store):
        messages = []
        # User Message
        user_message = ChatbaseAnalytics.get_default_payload(tracker, tracker_store,
                                                             latest_turn['user_event']['timestamp'], platform, 'user')
        user_message['message'] = latest_turn['user_event']['text']
        if 'intent' in latest_turn:
            user_message['intent'] = latest_turn['intent']
        no_response = not len(list(filter(lambda r: r.startswith('utter'), latest_turn['response_names'])))
        if no_response or 'intent' not in latest_turn:
            user_message['not_handled'] = True
        messages.append(user_message)
        # Agent Messages
        for response in latest_turn['bot_events']:
            bot_message = ChatbaseAnalytics.get_default_payload(tracker, tracker_store,
                                                                response['timestamp'], platform, 'agent')
            bot_message['message'] = response['text']
            messages.append(bot_message)
        self.post_async(messages)

    @staticmethod
    def get_default_payload(tracker, tracker_store, timestamp, platform, type):
        payload = {
                'api_key': tracker_store.chatbase_api_key,
                'type': type,
                'user_id': tracker.sender_id,
                'time_stamp': timestamp,
                'platform': platform,
                'version': tracker_store.chatbase_version,
            }

        if type == 'user':
            payload['user_id'] = tracker.sender_id

        return payload

    def post_async(self, messages):
        logger.debug('CHATBASE POST: {}'.format(messages))
        session = FuturesSession()
        session.hooks['response'] = self.response_hook
        session.post('https://chatbase.com/api/messages', json={'messages': messages})

    @staticmethod
    def response_hook(response, *args, **kwargs):
        # parse the json storing the result on the response object
        if response.status_code != 200:
            reason = response.json() if response.status_code == 400 else response.reason
            logger.warning(
                "Error: post request to Chatbase API failed with status code {}: {}".format(response.status_code,
                                                                                            reason))
            return reason
        else:
            return response.json()
