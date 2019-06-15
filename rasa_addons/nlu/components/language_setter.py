from typing import Any, List, Optional, Text, Dict
from rasa.nlu.components import Component
from rasa.nlu.training_data import Message
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.model import Metadata


class LanguageSetter(Component):
    name = 'LanguageSetter'

    def __init__(self,
                 component_config:  Dict[Text, Any] = None,
                 language: Optional[List[Text]] = None) -> None:
        super(LanguageSetter, self).__init__(component_config)
        self.language = language

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        message.set("language", self.language, add_to_output=True)

    @classmethod
    def create(
        cls, component_config: Dict[Text, Any], config: RasaNLUModelConfig
    ) -> 'LanguageSetter':
        return cls(component_config,
                   config.language)

    @classmethod
    def load(cls,
             meta: Dict[Text, Any],
             model_dir: Text = None,
             model_metadata: Metadata = None,
             cached_component: Optional['LanguageSetter'] = None,
             **kwargs: Any
             ) -> 'LanguageSetter':
        return cls(meta, model_metadata.get("language"))
