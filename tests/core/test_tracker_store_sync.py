from rasa_addons.core.tracker_stores.botfront import BotfrontTrackerStore
from unittest.mock import MagicMock
from test_tracker_store_sync_data import *

# case where a client connect to a different rasa instance in between ( eg:rasa1, rasa2, rasa1 )
# the local data should be updated
def test_should_properly_update_tracker():

    testTrackerStore = BotfrontTrackerStore(domain=None, url='test')
    #tracker with 1 event
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker1 )
    testTrackerStore.retrieve('test')

    #tracker with  new 1 event
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker2)
    testTrackerStore.retrieve('test')
    assert (
            testTrackerStore.trackers['test'] == merged_tracker_1
        ) 


# case where a client connect to the same rasa instance everytime
# the local data should not be updated
def test_should_not_update_events():

    testTrackerStore = BotfrontTrackerStore(domain=None, url='test')
     #tracker with 1 event
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker1 )
    testTrackerStore.retrieve('test')

     #tracker with  new no new event
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker3)
    testTrackerStore.retrieve('test')
    assert (
            testTrackerStore.trackers['test'] == merged_tracker_2
        ) 
