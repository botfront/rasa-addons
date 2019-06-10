from typing import Any

from rasa.nlu.components import Component
from rasa.nlu.training_data import Message

from requests_futures.sessions import FuturesSession


class ActivityLogger(Component):
    name = 'rasa_addons.nlu.components.ActivityLogger'
    defaults = {
        'url': '0.0.0.0',
    }

    def __init__(self, component_config=None):
        super(ActivityLogger, self).__init__(component_config)
        assert 'url' in component_config, 'You must specify the url to use the ActivityLogger component'

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        session = FuturesSession()
        params = kwargs.get('request_params', None)
        if params is None:
            return

        if 'model' not in params or params.get('nolog', 'false') not in ['false', '0', '']:
            return

        output = self._message_dict(message)
        output['modelId'] = params.get('model')

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