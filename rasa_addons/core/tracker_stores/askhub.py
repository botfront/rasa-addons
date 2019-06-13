import logging
from requests_futures.sessions import FuturesSession
logger = logging.getLogger(__name__)


class AskHubAnalytics(object):

    def save(self, latest_turn, tracker, all_events, platform, tracker_store):
        payload = self.get_default_payload(
            tracker,
            all_events[-1]['timestamp'],
            tracker_store.askhub_api_key,
            tracker_store.askhub_response_format,
            latest_turn['language'],
        )

        # User message part
        if latest_turn['user_event']['text']:
            payload['userMessage'] = latest_turn['user_event']['text']
            if 'intent' in latest_turn:
                payload['tags'].append('INTENT_{}'.format(latest_turn['intent'].upper()))
                payload['tags'].append('PARSED')
            else:
                payload['tags'].append('UNPARSED')
            payload['tags'].append('ACTION_QR' if self.is_latest_message_payload(latest_turn) else 'ACTION_NLP')

        # Bot message part
        payload['botResponse'] = latest_turn['bot_events']
        for r in latest_turn['response_names']:
            payload['tags'].append('RESPONSE_{}'.format(r.upper()))
        if platform:
            payload['tags'].append('FILTER_INTERFACE_{}'.format(platform.upper()))
        if 'entities' in latest_turn['parse_data']:
            payload['entities'] = AskHubAnalytics.get_entities(latest_turn)

        AskHubAnalytics.post_async(payload)

    @staticmethod
    def get_entities(latest_turn):
        def convert(entity):
            return {
                'type': 'simple',
                'title': entity['entity'],
                'value': entity['value']
            }

        parse_data = latest_turn['parse_data']
        if 'entities' in parse_data:
            return list(map(convert, parse_data['entities']))
        return None


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

    @staticmethod
    def post_async(payload):

        logger.debug('ASKHUB POST: {}'.format(payload))
        session = FuturesSession()
        session.hooks['response'] = AskHubAnalytics.response_hook
        session.post(' https://api.askhub.io/v1/event', json=payload)

    @staticmethod
    def is_latest_message_payload(latest_turn):
        if latest_turn['user_event']['text']:
            return latest_turn['user_event']['text'].startswith('/')
        return False

    @staticmethod
    def get_default_payload(tracker, timestamp, askhub_api_key, askhub_response_format, language):
        return {
                'token': askhub_api_key,
                'finalUserId': tracker.sender_id,
                'sessionId': tracker.sender_id,
                'timeStamp': round(timestamp * 1000),
                # 'userMessage': event['text'],
                'responseFormat': askhub_response_format,
                'language': language,
                'tags': [],
            }
