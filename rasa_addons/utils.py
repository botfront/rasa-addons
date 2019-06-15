
import logging

logger = logging.getLogger(__name__)


def get_latest_parse_data_language(all_events):
    events = reversed(all_events)
    try:
        while True:
            event = next(events)
            if event['event'] == 'user' and 'parse_data' in event and 'language' in event['parse_data']:
                return event['parse_data']['language']

    except StopIteration:
        return None
