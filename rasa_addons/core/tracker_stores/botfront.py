import logging
import jsonpickle
import requests
import time
from threading import Thread

from rasa.core.tracker_store import TrackerStore
from rasa.core.trackers import DialogueStateTracker, EventVerbosity

logger = logging.getLogger(__name__)

jsonpickle.set_preferred_backend('json')
jsonpickle.set_encoder_options('json', ensure_ascii=False)


class UnsynchronizedTracker:
    # Want these objects to behave just like tracker dict
    def __init__(self, tracker=None):
        self.tracker = tracker

    def __getitem__(self, i):
        return self.tracker[i]

    def __setitem__(self, i, value):
        self.tracker[i] = value

    def is_initialized(self):
        return self.tracker is not None


def _start_sweeper(tracker_store, break_time):
    while True:
        try:
            tracker_store.sweep()
        finally:
            time.sleep(break_time)


class BotfrontTrackerStore(TrackerStore):
    def __init__(self, domain, url, **kwargs):
        self.front_project_id = kwargs.get('project_id')
        self.front_url = url
        self.tracker_persist_time = kwargs.get('tracker_persist_time', 3600)
        self.max_events = kwargs.get('max_events', 100)

        self.trackers = {}
        self.sweeper = Thread(target=_start_sweeper, args=(self, 30))
        self.sweeper.setDaemon(True)
        self.sweeper.start()

        super(BotfrontTrackerStore, self).__init__(domain)

    def _fetch_tracker(self, sender_id):
        if not sender_id in self.trackers:
            tracker = self._get(sender_id)
            self.trackers[sender_id] = tracker

        return self.trackers[sender_id]

    def _url(self, sender_id, append):
        return '{url}/project/{project_id}/conversations/{sender_id}/{append}'.format(url=self.front_url,
                                                                                      project_id=self.front_project_id,
                                                                                      sender_id=sender_id,
                                                                                      append=append
                                                                                      )

    def _get(self, sender_id):
        logger.debug('{} -> GET request for tracker'.format(sender_id))

        try:
            response = requests.get(self._url(sender_id, self.max_events), timeout=1)
            if response.status_code == 200:
                return response.json()  # Tracker object or None if none in database

            message = response.json() if response.status_code == 400 else response.reason
            logger.warning(
                'Error: get request to botfront-api failed with status code {}: {}'.format(response.status_code,
                                                                                           message))
        except Exception as e:
            logger.error(
                'Error: get request to botfront-api failed with error: {}'.format(e))

        return UnsynchronizedTracker()  # Return an object to represent synchronization failure with database

    def _post(self, sender_id, method, payload):
        url = self._url(sender_id, method)

        try:
            response = requests.post(url, json=payload, timeout=1)
            if response.status_code != 200:
                message = response.json() if response.status_code == 400 else response.reason
                logger.warning(
                    "Error: post request to botfront-api failed with status code {}: {}".format(response.status_code,
                                                                                                message))
        except Exception as e:
            logger.error(
                'Error: post request to botfront-api failed with error: {}'.format(e))

    @staticmethod
    def _is_none(tracker):
        return tracker is None or (isinstance(tracker, UnsynchronizedTracker) and not tracker.is_initialized())

    def save(self, canonical_tracker):

        # Fetch here just in case retrieve wasn't called first
        sender_id = canonical_tracker.sender_id
        tracker = self._fetch_tracker(sender_id)
        serialized_tracker = self._serialize_tracker_to_dict(canonical_tracker)

        if self._is_none(tracker):
            # No document in the collection, so insert one

            if not isinstance(tracker, UnsynchronizedTracker):
                logger.debug('{} -> INSERTING TRACKER: {}'.format(sender_id, serialized_tracker))
                self._post(sender_id, 'insert', serialized_tracker)
                self.trackers[sender_id] = serialized_tracker
            else:
                logger.debug('{} -> UNSYNCHRONIZED TRACKER UPDATE'.format(sender_id))
                self.trackers[sender_id] = UnsynchronizedTracker(serialized_tracker)

            return serialized_tracker['events']

        # Insert only the new examples
        last_timestamp = (next(reversed(tracker['events']), {})).get('timestamp', None)
        new_events = list(filter(lambda x: x['timestamp'] > last_timestamp, serialized_tracker['events']))

        if not isinstance(tracker, UnsynchronizedTracker):
            tracker_shallow_copy = {key: val for key, val in serialized_tracker.items()}
            tracker_shallow_copy['events'] = new_events

            logger.debug('{} -> UPDATING TRACKER: {}'.format(sender_id, tracker_shallow_copy))
            self._post(sender_id, 'update', tracker_shallow_copy)
            self.trackers[sender_id] = serialized_tracker
        else:
            logger.debug('{} -> UNSYNCHRONIZED TRACKER UPDATE'.format(sender_id))
            self.trackers[sender_id] = UnsynchronizedTracker(serialized_tracker)

        return serialized_tracker['events']

    def _init_tracker(self, sender_id, tracker):
        if self.domain:
            return DialogueStateTracker.from_dict(sender_id,
                                                  tracker["events"],
                                                  self.domain.slots)

        else:
            logger.warning("Can't recreate tracker from mongo storage "
                           "because no domain is set. Returning `None` "
                           "instead.")
            return None

    def retrieve(self, sender_id):
        tracker = self._fetch_tracker(sender_id)

        if not self._is_none(tracker):
            return self._init_tracker(sender_id, tracker)

        return None

    def sweep(self):
        # Iterate over list of keys to prevent runtime errors when deleting elements
        for key in list(self.trackers.keys()):
            tracker = self.trackers[key]
            if not self._is_none(tracker) and tracker['latest_event_time'] < time.time() - self.tracker_persist_time:
                logger.debug('SWEEPER: Removing tracker for user {}'.format(key))
                del self.trackers[key]

    @staticmethod
    def _serialize_tracker_to_dict(canonical_tracker):
        return canonical_tracker.current_state(EventVerbosity.ALL)


