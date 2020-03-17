import logging
import jsonpickle
import requests
import time
import asyncio
import os
from threading import Thread

from rasa.core.tracker_store import TrackerStore
from rasa.core.trackers import DialogueStateTracker, EventVerbosity

from sgqlc.endpoint.http import HTTPEndpoint
import urllib.error

logger = logging.getLogger(__name__)

jsonpickle.set_preferred_backend("json")
jsonpickle.set_encoder_options("json", ensure_ascii=False)

print('hum')
GET_TRACKER = """
query trackerStore(
    $senderId: String!
    $projectId: String!
    $after: Int
    $maxEvents: Int
) {
   trackerStore(senderId: $senderId, projectId:$projectId, after:$after, maxEvents:$maxEvents) {
       	tracker
        lastIndex
        lastTimestamp
    }
}
"""

INSERT_TRACKER = """
mutation insertTracker(
    $senderId: String!
    $projectId: String!
    $tracker: Any
) {
   insertTrackerStore(senderId: $senderId, projectId:$projectId, tracker:$tracker)
}
"""

UPDATE_TRACKER = """
mutation updateTracker(
    $senderId: String!
    $projectId: String!
    $tracker: Any
) {
   updateTracker(senderId: $senderId, projectId: $projectId, tracker: $tracker)
}
"""


def _start_sweeper(tracker_store, break_time):
    while True:
        try:
            tracker_store.sweep()
        finally:
            time.sleep(break_time)


class BotfrontTrackerStore(TrackerStore):
    def __init__(self, domain, url, **kwargs):
       
        self.project_id = kwargs.get("project_id")
        self.tracker_persist_time = kwargs.get("tracker_persist_time", 3600)
        self.max_events = kwargs.get("max_events", 100)
        self.trackers = {}
        self.trackers_info = (
            {}
        )  # in this stucture we will keep the last index and the last timestamp of events in the db for a said tracker
        self.sweeper = Thread(target=_start_sweeper, args=(self, 30))
        self.sweeper.setDaemon(True)
        self.sweeper.start()
        api_key = os.environ.get("API_KEY")
        headers = [{"Authorization": api_key}] if api_key else []
        self.graphql_endpoint = HTTPEndpoint(url, *headers)
        super(BotfrontTrackerStore, self).__init__(domain)
        logger.debug("BotfrontTrackerStore tracker store created")

    async def _graphql_query(self, query, params):
        try:
            response = self.graphql_endpoint(query, params)
            if "errors" in response and response["errors"]:
                raise urllib.error.URLError("Null response.")
            return response["data"]
        except urllib.error.URLError:
            logger.debug(f"something went wrong with the query {GET_TRACKER}")
            return None

    async def _fetch_tracker(self, sender_id, lastIndex):
        data = await self._graphql_query(
            GET_TRACKER,
            {
                "senderId": sender_id,
                "projectId": self.project_id,
                "after": lastIndex,
                "maxEvents": self.max_events,
            },
        )
        return data["trackerStore"]

    async def _insert_tracker_gql(self, sender_id, tracker):
        data = await self._graphql_query(
            INSERT_TRACKER,
            {"senderId": sender_id, "projectId": self.project_id, "tracker": tracker},
        )
        return data["insertTracker"]

    async def _update_tracker_gql(self, sender_id, tracker):
        data = await self._graphql_query(
            UPDATE_TRACKER,
            {"senderId": sender_id, "projectId": self.project_id, "tracker": tracker},
        )
        return data["updateTracker"]

    def _get_last_index(sender_id):
        last_index = self.trackers_info[sender_id].last_index
        if last_index:
            return last_index
        return 0

    def _get_last_timestamp(sender_id):
        last_timestamp = self.trackers_info[sender_id].last_timestamp
        if last_timestamp:
            return last_timestamp
        return 0

    def _store_tracker_info(sender_id, tracker_info):
        self.trackers_info[sender_id] = {
            "last_index": tracker_info["lastIndex"],
            "last_timestamp": tracker_info["lastTimestamp"],
        }

    def save(self, canonical_tracker):

        # Fetch here just in case retrieve wasn't called first
        sender_id = canonical_tracker.sender_id
        tracker = self.trackers[sender_id]
        serialized_tracker = self._serialize_tracker_to_dict(canonical_tracker)

        if tracker is None:  # the tracker does not exist
            self._insert_tracker_gql(sender_id, serialized_tracker)
            self.trackers[sender_id] = serialized_tracker
            return serialized_tracker["events"]
        else:  # the tracker  exist
            # Insert only the new examples
            last_timestamp = _get_last_timestamp(sender_id)
            new_events = list(
                filter(
                    lambda x: x["timestamp"] > last_timestamp,
                    serialized_tracker["events"],
                )
            )
            tracker_shallow_copy = {key: val for key, val in serialized_tracker.items()}
            tracker_shallow_copy["events"] = new_events
            self._update_tracker_gql(sender_id, serialized_tracker)
            self.trackers[sender_id] = serialized_tracker
            return serialized_tracker["events"]

    def _convert_tracker(self, sender_id, tracker):
        if self.domain:
            return DialogueStateTracker.from_dict(
                sender_id, tracker["events"], self.domain.slots
            )
        else:
            logger.warning(
                "Can't recreate tracker from mongo storage "
                "because no domain is set. Returning `None` "
                "instead."
            )
            return None

    def _update_tracker(sender_id, remote_tracker):
        old_tracker = self.trackers[sender_id]
        if old_tracker is not None:
            events = old_tracker.events
            new_events = [*events, *new_tracker.events]
            new_tracker = {**old_tracker, **remote_tracker}
            new_tracker.events = new_events
            self.trackers[sender_id] = new_tracker
            return self.trackers[sender_id]
        return None

    def retrieve(self, sender_id):
        last_index = _get_last_index(sender_id)
        new_tracker_info = self._fetch_tracker(sender_id, last_index)
        self._store_tracker_info(new_tracker_info)
        tracker = self._update_tracker(sender_id, new_tracker_info.tracker)
        if self._update_tracker(sender_id, new_tracker):
            return self._convert_tracker(sender_id, tracker)
        return None

    def sweep(self):
        # Iterate over list of keys to prevent runtime errors when deleting elements
        for key in list(self.trackers.keys()):
            tracker = self.trackers[key]
            if (
                not self._is_none(tracker)
                and tracker["latest_event_time"]
                < time.time() - self.tracker_persist_time
            ):
                logger.debug("SWEEPER: Removing tracker for user {}".format(key))
                del self.trackers[key]

    @staticmethod
    def _serialize_tracker_to_dict(canonical_tracker):
        return canonical_tracker.current_state(EventVerbosity.ALL)

