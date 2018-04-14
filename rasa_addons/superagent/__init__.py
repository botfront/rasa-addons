import os
from rasa_addons.superagent.message_processor import SuperMessageProcessor
from rasa_core.agent import Agent
from rasa_core.domain import TemplateDomain
from rasa_core.featurizers import Featurizer
from rasa_core.interpreter import NaturalLanguageInterpreter
from rasa_core.policies.ensemble import PolicyEnsemble
from rasa_core.processor import MessageProcessor


class SuperAgent(Agent):
    def __init__(
            self,
            domain,  # type: Union[Text, Domain]
            policies=None,  # type: Optional[Union[PolicyEnsemble, List[Policy]]
            featurizer=None,  # type: Optional[Featurizer]
            interpreter=None,  # type: Optional[NaturalLanguageInterpreter]
            tracker_store=None,  # type: Optional[TrackerStore]
            allowed_entities_filename=None  # type: Optional[str]
    ):
        self.processor = None
        self.allowed_entities_filename = allowed_entities_filename
        super(SuperAgent, self).__init__(
            domain,
            policies,
            featurizer,
            interpreter,
            tracker_store
        )

    @classmethod
    def load(cls, path, interpreter=None, tracker_store=None,
             action_factory=None, rules_file=None):
        # type: (Text, Any, Optional[TrackerStore]) -> Agent

        if path is None:
            raise ValueError("No domain path specified.")
        domain = TemplateDomain.load(os.path.join(path, "domain.yml"),
                                     action_factory)
        # ensures the domain hasn't changed between test and train
        domain.compare_with_specification(path)
        featurizer = Featurizer.load(path)
        ensemble = PolicyEnsemble.load(path, featurizer)
        _interpreter = NaturalLanguageInterpreter.create(interpreter)
        _tracker_store = cls.create_tracker_store(tracker_store, domain)
        return cls(domain, ensemble, featurizer, _interpreter, _tracker_store, rules_file)

    def _create_processor(self, preprocessor=None):
        # type: (Callable[[Text], Text]) -> MessageProcessor
        """Instantiates a processor based on the set state of the agent."""

        self._ensure_agent_is_prepared()
        self.processor = SuperMessageProcessor(self.interpreter, self.policy_ensemble, self.domain, self.tracker_store,
                                               message_preprocessor=preprocessor,
                                               rules=self.allowed_entities_filename)
        return self.processor
