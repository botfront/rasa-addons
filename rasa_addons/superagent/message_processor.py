from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.superagent.dismabiguator import ActionDisambiguate
from rasa_addons.superagent.rules import Rules
from rasa_core.events import UserUttered
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
                 create_dispatcher=None,  # type: Optional[LambdaType]
                 rules_file=None  # type: Optional[str]
                 ):

        self.rules = Rules(rules_file) if rules_file is not None else None
        super(SuperMessageProcessor, self).__init__(
            interpreter,
            policy_ensemble,
            domain,
            tracker_store,
            max_number_of_predictions,
            message_preprocessor,
            on_circuit_break
        )
        self.create_dispatcher = create_dispatcher
        if self.create_dispatcher is None:
            self.create_dispatcher = lambda sender_id, output_channel, dom: Dispatcher(sender_id, output_channel, dom)

    def _handle_message_with_tracker(self, message, tracker):
        # type: (UserMessage, DialogueStateTracker) -> None

        parse_data = self._parse_message(message)

        # rules section #
        if self._rule_interrupts(parse_data, tracker, message):
            return
        # rules section - end #

        # don't ever directly mutate the tracker
        # - instead pass its events to log
        tracker.update(UserUttered(message.text, parse_data["intent"],
                                   parse_data["entities"], parse_data))
        # store all entities as slots
        for e in self.domain.slots_for_entities(parse_data["entities"]):
            tracker.update(e)

        logger.debug("Logged UserUtterance - "
                     "tracker now has {} events".format(len(tracker.events)))

    def _rule_interrupts(self, parse_data, tracker, message):
        if self.rules is not None:
            dispatcher = self.create_dispatcher(message.sender_id, message.output_channel, self.domain)
            return self.rules.interrupts(dispatcher, parse_data, tracker, self._run_action)

    def _predict_and_execute_next_action(self, message, tracker):
        # this will actually send the response to the user

        dispatcher = self.create_dispatcher(message.sender_id, message.output_channel, self.domain)
        # keep taking actions decided by the policy until it chooses to 'listen'
        should_predict_another_action = True
        num_predicted_actions = 0
        self._log_slots(tracker)

        # action loop. predicts actions until we hit action listen
        while (should_predict_another_action
               and self._should_handle_message(tracker)
               and num_predicted_actions < self.max_number_of_predictions):
            # this actually just calls the policy's method by the same name
            action = self._get_next_action(tracker)

            should_predict_another_action = self._run_action(action,
                                                             tracker,
                                                             dispatcher)
            num_predicted_actions += 1

        if (num_predicted_actions == self.max_number_of_predictions and
                should_predict_another_action):
            # circuit breaker was tripped
            logger.warn(
                "Circuit breaker tripped. Stopped predicting "
                "more actions for sender '{}'".format(tracker.sender_id))
            if self.on_circuit_break:
                # call a registered callback
                self.on_circuit_break(tracker, dispatcher)
