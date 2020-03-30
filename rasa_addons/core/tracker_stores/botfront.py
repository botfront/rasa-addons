import logging
import jsonpickle
import requests
import time
import os
from threading import Thread

from rasa.core.tracker_store import TrackerStore
from rasa.core.trackers import DialogueStateTracker, EventVerbosity

from sgqlc.endpoint.http import HTTPEndpoint
import urllib.error

logger = logging.getLogger(__name__)

jsonpickle.set_preferred_backend("json")
jsonpickle.set_encoder_options("json", ensure_ascii=False)

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
   insertTrackerStore(senderId: $senderId, projectId:$projectId, tracker:$tracker){
        lastIndex
        lastTimestamp
    }
}
"""

UPDATE_TRACKER = """
mutation updateTracker(
    $senderId: String!
    $projectId: String!
    $tracker: Any
) {
   updateTrackerStore(senderId: $senderId, projectId: $projectId, tracker: $tracker){
        lastIndex
        lastTimestamp
    }
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

        self.project_id = os.environ.get("BF_PROJECT_ID")
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

    def _graphql_query(self, query, params):
        try:
            response = self.graphql_endpoint(query, params)
            if response.get("errors") is not None and response.get("data") is None:
                raise urllib.error.URLError("Null response.")
            return response["data"]
        except urllib.error.URLError:
            logger.debug(f"something went wrong with the query {GET_TRACKER}")
            return {}

    def _fetch_tracker(self, sender_id, lastIndex):
        data = self._graphql_query(
            GET_TRACKER,
            {
                "senderId": sender_id,
                "projectId": self.project_id,
                "after": lastIndex,
                "maxEvents": self.max_events,
            },
        )
        return data.get("trackerStore")

    def _insert_tracker_gql(self, sender_id, tracker):
        data = self._graphql_query(
            INSERT_TRACKER,
            {"senderId": sender_id, "projectId": self.project_id, "tracker": tracker},
        )
        return data.get("insertTrackerStore")

    def _update_tracker_gql(self, sender_id, tracker):
        data = self._graphql_query(
            UPDATE_TRACKER,
            {"senderId": sender_id, "projectId": self.project_id, "tracker": tracker},
        )
        return data.get("updateTrackerStore")

    def _get_last_index(self, sender_id):
        info = self.trackers_info.get(sender_id, -1)
        if info == -1:
            return info
        elif info.get("last_index") is None:
            return -1
        else:
            return info.get("last_index")

    def _get_last_timestamp(self, sender_id):
        info = self.trackers_info.get(sender_id, 0)
        if info == 0:
            return info
        elif info.get("last_timestamp") is None:
            return 0
        else:
            return info.get("last_timestamp")

    def _store_tracker_info(self, sender_id, tracker_info):
        if tracker_info is not None:
            self.trackers_info[sender_id] = {
                "last_index": tracker_info["lastIndex"],
                "last_timestamp": tracker_info["lastTimestamp"],
            }

    def save(self, canonical_tracker):

        # Fetch here just in case retrieve wasn't called first
        sender_id = canonical_tracker.sender_id
        tracker = self.trackers.get(sender_id)
        serialized_tracker = self._serialize_tracker_to_dict(canonical_tracker)

        if tracker is None:  # the tracker does not exist localy ( first save)
            updated_info = self._insert_tracker_gql(sender_id, serialized_tracker)
            self.trackers[sender_id] = serialized_tracker
            # update the last index and last time stamp for future uses
            self._store_tracker_info(sender_id, updated_info)
            return serialized_tracker["events"]
        else:  # the tracker  exist localy
            # Insert only the new examples
            last_timestamp = self._get_last_timestamp(sender_id)
            new_events = list(
                filter(
                    lambda x: x["timestamp"] > last_timestamp,
                    serialized_tracker["events"],
                )
            )
            tracker_shallow_copy = {key: val for key, val in serialized_tracker.items()}
            tracker_shallow_copy["events"] = new_events
            # only send the new events to the remote tracker
            updated_info = self._update_tracker_gql(sender_id, tracker_shallow_copy)
            # update the last index and last time stamp for future uses
            self._store_tracker_info(sender_id, updated_info)
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

    def _update_tracker(self, sender_id, remote_tracker):
        old_tracker = self.trackers.get(sender_id)
        if old_tracker is not None:
            events = old_tracker.get("events")
            remote_events = remote_tracker.get("events")
            # if we recieve max event it means that the we skiped some events
            # as we take only the last max events, so we remplace the local copy with the remote data
            if len(remote_events) == self.max_events:
                new_events = remote_events
            else:
                new_events = [*events, *remote_events]
            new_tracker = {**old_tracker, **remote_tracker}
            new_tracker["events"] = new_events
            self.trackers[sender_id] = new_tracker
            return new_tracker
        else:
            self.trackers[sender_id] = remote_tracker
            return remote_tracker

    def retrieve(self, sender_id):
        last_index = self._get_last_index(sender_id)
        # retreive all new info since the last sync (given by last index)
        new_tracker_info = self._fetch_tracker(sender_id, last_index)
        current_tracker = self.trackers.get(sender_id)
        # do not chane the order of these ifs 
        # ortherwise you will get synchornication issues when working with multiple rasa instances
        # the tracker exist on the remote and may exist locally
        if new_tracker_info is not None:
            self._store_tracker_info(sender_id, new_tracker_info)
            tracker = self._update_tracker(sender_id, new_tracker_info.get("tracker"))
            return self._convert_tracker(sender_id, tracker)
       
        
        # the tracker do not exist yet
        if current_tracker is None: return None

         # the tracker exist localy an there is no new infos
        return self._convert_tracker(sender_id, current_tracker)

    def sweep(self):
        # Iterate over list of keys to prevent runtime errors when deleting elements
        for key in list(self.trackers.keys()):
            tracker = self.trackers.get(key)
            if (
                tracker is not None
                and tracker.get("latest_event_time", float("inf")) < time.time() - self.tracker_persist_time
            ):
                logger.debug("SWEEPER: Removing tracker for user {}".format(key))
                del self.trackers[key]

    @staticmethod
    def _serialize_tracker_to_dict(canonical_tracker):
        return canonical_tracker.current_state(EventVerbosity.ALL)

