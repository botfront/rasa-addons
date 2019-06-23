from typing import Any

from rasa.nlu.components import Component
from rasa.nlu.training_data import Message

from requests_futures.sessions import FuturesSession
import json
import logging

logger = logging.getLogger(__name__)

class HttpLogger(Component):
    name = 'HttpLogger'
    defaults = {
        'url': '0.0.0.0',
        'params': {},  # Params added to the json payload
    }

    def __init__(self, component_config=None):
        super(HttpLogger, self).__init__(component_config)
        assert 'url' in component_config, 'You must specify the url to use the HttpLogger component'
        assert 'model_id' in component_config, 'You must specify the model_id to use the HttpLogger component'

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        session = FuturesSession()
        if not message.params: message.params = {}
        if message.params.get('nolog', 'false') in ['true', '1']:
            return

        output = self._message_dict(message)
        for k, v in self.component_config.get('params').items():
            output[k] = v
        output['modelId'] = self.component_config.get('model_id')

        future = session.post(self.component_config.get('url'), json=output)
        response = future.result()
        if response.status_code != 200:
            logger.error('{} Error from API: {}'.format(str(response.status_code), json.loads(response.content)['error']))

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