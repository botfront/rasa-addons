from typing import Any

from rasa.nlu.components import Component
from rasa.nlu.training_data import Message

from requests_futures.sessions import FuturesSession


class HttpLogger(Component):
    name = 'HttpLogger'
    defaults = {
        'url': '0.0.0.0',
        'params': {},  # Params added to the json payload
    }

    def __init__(self, component_config=None):
        super(HttpLogger, self).__init__(component_config)
        assert 'url' in component_config, 'You must specify the url to use the HttpLogger component'

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        session = FuturesSession()
        if not message.params or message.params.get('nolog', 'false') not in ['true', '1']:
            return

        output = self._message_dict(message)
        for k, v in self.component_config.get('params').items():
            output[k] = v

        session.post(self.component_config.get('url'), json=output)

    @staticmethod
    def _message_dict(message):
        obj = {
            'text': '',
            'intent': {
                'name': None,
                'confidence': 0,
            },
            'entities': [],
        }
        obj.update(message.as_dict(only_output_properties=True))

        intent = obj['intent']

        obj.update({
            'intent': intent['name'],
            'confidence': intent['confidence'],
        })

        # Botfront expects no intent if intent is None
        if obj['intent'] is None:
            del obj['intent']

        return obj