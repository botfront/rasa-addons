import logging
import jsonpickle
import requests
import time
import os
from threading import Thread
import sys
from rasa.core.tracker_store import TrackerStore
from rasa.core.trackers import DialogueStateTracker, EventVerbosity
from guppy import hpy

h = hpy()

from sgqlc.endpoint.http import HTTPEndpoint
import urllib.error

logger = logging.getLogger(__name__)
logging.getLogger("sgqlc.endpoint.http").setLevel(logging.WARNING)

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
    $env: Environement
) {
    insertTrackerStore(senderId: $senderId, projectId:$projectId, tracker:$tracker, env: $env){
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
    $env: Environement
) {
    updateTrackerStore(senderId: $senderId, projectId: $projectId, tracker: $tracker, env: $env){
        lastIndex
        lastTimestamp
    }
}
"""


class DummyTrackerStore(TrackerStore):
    def __init__(self, domain, url, **kwargs):

        super(DummyTrackerStore, self).__init__(domain)
        logger.debug("DummyTrackerStore tracker store created")

    def save(self, canonical_tracker):
        return None

    # Fetch here just in case retrieve wasn't called first

    def retrieve(self, sender_id):
        return None
