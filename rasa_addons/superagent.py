import os
import logging
from rasa_core.agent import Agent
from rasa_core.domain import TemplateDomain
from rasa_core.interpreter import NaturalLanguageInterpreter
from rasa_core.nlg import NaturalLanguageGenerator
from rasa_core.policies.ensemble import PolicyEnsemble
from rasa_core.events import UserUttered
from rasa_core.processor import MessageProcessor
from rasa_core.dispatcher import Dispatcher
from rasa_addons.disambiguation import ActionDisambiguate
from rasa_addons.rules import Rules
from rasa_core.utils import EndpointConfig

logging.basicConfig()
logger = logging.getLogger()


class SuperAgent(Agent):
    def __init__(
            self,
            domain,  # type: Union[Text, Domain]
            policies=None,  # type: Optional[Union[PolicyEnsemble, List[Policy]]
            interpreter=None,  # type: Optional[NaturalLanguageInterpreter]
            generator=None,  # type: Union[EndpointConfig, NLG]
            tracker_store=None,  # type: Optional[TrackerStore]
            action_endpoint=None,  # type: Optional[EndpointConfig]
            fingerprint=None,  # type: Optional[Text]
            create_dispatcher=None,  # type: Optional[LambdaType]
            create_nlg=None,  # type: Optional[LambdaType],
            rules=None,  # type: Optional[EndpointConfig, str]
    ):
        self.processor = None
        self.create_dispatcher = create_dispatcher
        self.create_nlg = create_nlg

        self.rules = self.get_rules(rules)
        # Initializing variables with the passed parameters.
        self.domain = self._create_domain(domain)
        self.policy_ensemble = self._create_ensemble(policies)

        if not isinstance(interpreter, NaturalLanguageInterpreter):
            if interpreter is not None:
                logger.warning(
                    "Passing a value for interpreter to an agent "
                    "where the value is not an interpreter "
                    "is deprecated. Construct the interpreter, before"
                    "passing it to the agent, e.g. "
                    "`interpreter = NaturalLanguageInterpreter.create("
                    "nlu)`.")
            interpreter = NaturalLanguageInterpreter.create(interpreter, None)

        self.interpreter = interpreter

        self.nlg = NaturalLanguageGenerator.create(generator, self.domain) if self.create_nlg is None else self.create_nlg(generator, self.domain)
        self.tracker_store = self.create_tracker_store(
            tracker_store, self.domain)
        self.action_endpoint = action_endpoint

        self._set_fingerprint(fingerprint)

    def get_rules(self, rules_source):
        if isinstance(rules_source, EndpointConfig):
            return Rules.load_from_remote(rules_source)
        elif isinstance(rules_source, str):
            return Rules.load_from_file(rules_source)
        elif rules_source is not None:
            raise ValueError('Rules must be either a path to a yaml file, or an endpoint of which the GET method '
                             'returns rules in a JSON format')
        else:
            return None

    @classmethod
    def load(cls,
             path,
             domain=None,
             policies=None,
             interpreter=None,
             generator=None,
             tracker_store=None,
             action_endpoint=None,
             rules=None,
             create_dispatcher=None,
             create_nlg=None):
        # type: (Text, Any, Optional[TrackerStore]) -> Agent

        if not path:
            raise ValueError("You need to provide a valid directory where "
                             "to load the agent from when calling "
                             "`Agent.load`.")

        if os.path.isfile(path):
            raise ValueError("You are trying to load a MODEL from a file "
                             "('{}'), which is not possible. \n"
                             "The persisted path should be a directory "
                             "containing the various model files. \n\n"
                             "If you want to load training data instead of "
                             "a model, use `agent.load_data(...)` "
                             "instead.".format(path))

        if domain is None:
            domain = TemplateDomain.load(os.path.join(path, "domain.yml"))
        if policies is None:
            policies = PolicyEnsemble.load(path)

        # ensures the domain hasn't changed between test and train
        domain.compare_with_specification(path)
        #
        # _interpreter = NaturalLanguageInterpreter.create(interpreter)
        # _tracker_store = cls.create_tracker_store(tracker_store, domain)
        return cls(
                domain=domain,
                policies=policies,
                interpreter=interpreter,
                tracker_store=tracker_store,
                generator=generator,
                action_endpoint=action_endpoint,
                rules=rules,
                create_dispatcher=create_dispatcher,
                create_nlg=create_nlg
        )

    def create_processor(self, preprocessor=None):
        # type: (Callable[[Text], Text]) -> MessageProcessor
        """Instantiates a processor based on the set state of the agent."""

        self._ensure_agent_is_ready()
        self.processor = SuperMessageProcessor(self.interpreter,
                                               self.policy_ensemble,
                                               self.domain,
                                               self.tracker_store,
                                               self.nlg,
                                               message_preprocessor=preprocessor,
                                               action_endpoint=self.action_endpoint,
                                               create_dispatcher=self.create_dispatcher,
                                               rules_file=self.rules_file)
        return self.processor


class SuperMessageProcessor(MessageProcessor):
    def __init__(self,
                 interpreter,  # type: NaturalLanguageInterpreter
                 policy_ensemble,  # type: PolicyEnsemble
                 domain,  # type: Domain
                 tracker_store,  # type: TrackerStore
                 generator,  # type: NaturalLanguageGenerator
                 action_endpoint=None,  # type: Optional[EndpointConfig]
                 max_number_of_predictions=10,  # type: int
                 message_preprocessor=None,  # type: Optional[LambdaType]
                 on_circuit_break=None,  # type: Optional[LambdaType]
                 create_dispatcher=None,  # type: Optional[LambdaType]
                 rules_file=None  # type: Optional[str]
                 ):

        self.rules = rules
        super(SuperMessageProcessor, self).__init__(
            interpreter,
            policy_ensemble,
            domain,
            tracker_store,
            generator,
            action_endpoint,
            max_number_of_predictions,
            message_preprocessor,
            on_circuit_break
        )

        self.create_dispatcher = create_dispatcher
        if self.create_dispatcher is None:
            self.create_dispatcher = lambda sender_id, output_channel, nlg: Dispatcher(sender_id, output_channel, nlg)

    def _handle_message_with_tracker(self, message, tracker):
        # type: (UserMessage, DialogueStateTracker) -> None

        if message.parse_data:
            parse_data = message.parse_data
        else:
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
            dispatcher = self.create_dispatcher(message.sender_id, message.output_channel, self.nlg)
            return self.rules.interrupts(dispatcher, parse_data, tracker, self._run_action)

    def _predict_and_execute_next_action(self, message, tracker):
        # this will actually send the response to the user

        dispatcher = self.create_dispatcher(message.sender_id,
                                            message.output_channel,
                                            self.nlg)
        # keep taking actions decided by the policy until it chooses to 'listen'
        should_predict_another_action = True
        num_predicted_actions = 0

        self._log_slots(tracker)

        # action loop. predicts actions until we hit action listen
        while (should_predict_another_action
               and self._should_handle_message(tracker)
               and num_predicted_actions < self.max_number_of_predictions):
            # this actually just calls the policy's method by the same name
            action, policy, confidence = self.predict_next_action(tracker)

            should_predict_another_action = self._run_action(action,
                                                             tracker,
                                                             dispatcher,
                                                             policy,
                                                             confidence)
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

