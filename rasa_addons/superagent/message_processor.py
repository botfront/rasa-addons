from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

from rasa_addons.superagent.allowed_entities import AllowedEntities
from rasa_core.actions import Action
from rasa_core.events import UserUttered, ActionExecuted, SlotSet, UserUtteranceReverted, ActionReverted
from rasa_core.processor import MessageProcessor
from rasa_core.dispatcher import Dispatcher

import logging

logger = logging.getLogger(__name__)


class SuperMessageProcessor(MessageProcessor):
    def __init__(self,
                 interpreter,  # type: NaturalLanguageInterpreter
                 policy_ensemble,  # type: PolicyEnsemble
                 domain,  # type: Domain
                 tracker_store,  # type: TrackerStore
                 max_number_of_predictions=10,  # type: int
                 message_preprocessor=None,  # type: Optional[LambdaType]
                 on_circuit_break=None,  # type: Optional[LambdaType]
                 allowed_entities_file=None  # type: Optional[str]
                 ):

        if allowed_entities_file is not None:
            self.allowed_entities = AllowedEntities(allowed_entities_file)
        super(SuperMessageProcessor, self).__init__(
            interpreter,
            policy_ensemble,
            domain,
            tracker_store,
            max_number_of_predictions,
            message_preprocessor,
            on_circuit_break
        )

    def _handle_message_with_tracker(self, message, tracker):
        # type: (UserMessage, DialogueStateTracker) -> None

        parse_data = self._parse_message(message)

        if self.allowed_entities:
            self.allowed_entities.filter_entities(parse_data)

        # don't ever directly mutate the tracker
        # - instead pass its events to log
        tracker.update(UserUttered(message.text, parse_data["intent"],
                                   parse_data["entities"], parse_data))
        # store all entities as slots
        for e in self.domain.slots_for_entities(parse_data["entities"]):
            tracker.update(e)

        logger.debug("Logged UserUtterance - "
                     "tracker now has {} events".format(len(tracker.events)))

    def _clear_unexpected_entities(self, parse_data):
        filtered = filter(lambda ent: ent['entity'] in self.allowed_entities[parse_data['intent']['name']],
                          parse_data['entities'])
        if len(filtered) < len(parse_data['entities']):
            # logging first
            logger.warn("entity(ies) were removed from parse stories")
            parse_data['entities'] = filtered


