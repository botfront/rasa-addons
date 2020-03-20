from rasa_addons.core.tracker_stores.botfront import BotfrontTrackerStore
from unittest.mock import MagicMock
from test_tracker_store_sync_data import *

def test_should_properly_update_tracker():

    testTrackerStore = BotfrontTrackerStore(domain=None, url='test')
    
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker1 )
    testTrackerStore.retrieve('test')

    
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker2)
    testTrackerStore.retrieve('test')
    assert (
            testTrackerStore.trackers['test'] == merged_tracker_1
        ) 



def test_should_not_update_events():

    testTrackerStore = BotfrontTrackerStore(domain=None, url='test')
    
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker1 )
    testTrackerStore.retrieve('test')

    
    testTrackerStore._fetch_tracker = MagicMock(return_value = tracker3)
    testTrackerStore.retrieve('test')
    assert (
            testTrackerStore.trackers['test'] == merged_tracker_2
        ) 
