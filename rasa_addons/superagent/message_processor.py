from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_addons.superagent.input_validator import ActionInvalidUtterance
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
                 rules_file=None  # type: Optional[str]
                 ):

        if rules_file is not None:
            self.rules = Rules(rules_file)
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

        if self.rules:
            self.rules.substitute_intent(parse_data, tracker)
            self.rules.filter_entities(parse_data)

            error_template = self.rules.input_validation.get_error(parse_data, tracker)
            if error_template is not None:
                self._utter_error_and_roll_back(message, tracker, error_template)
                return

        # don't ever directly mutate the tracker
        # - instead pass its events to log
        tracker.update(UserUttered(message.text, parse_data["intent"],
                                   parse_data["entities"], parse_data))
        # store all entities as slots
        for e in self.domain.slots_for_entities(parse_data["entities"]):
            tracker.update(e)

        logger.debug("Logged UserUtterance - "
                     "tracker now has {} events".format(len(tracker.events)))

    def _utter_error_and_roll_back(self, latest_bot_message, tracker, template):
        dispatcher = Dispatcher(latest_bot_message.sender_id,
                                latest_bot_message.output_channel,
                                self.domain)

        action = ActionInvalidUtterance(template)

        self._run_action(action, tracker, dispatcher)
