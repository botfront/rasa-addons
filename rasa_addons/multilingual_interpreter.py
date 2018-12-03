from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from rasa_core.utils import EndpointConfig
import json
import logging
import requests
from rasa_core import constants
logger = logging.getLogger(__name__)

INTENT_MESSAGE_PREFIX = "/"

from rasa_core.interpreter import NaturalLanguageInterpreter, RasaNLUHttpInterpreter

class RasaMultiNLUHttpInterpreter(RasaNLUHttpInterpreter):
    def __init__(self, models=None, endpoint=None, project_name='default'):
        # type: (Text, EndpointConfig, Text) -> None

        self.models = models
        self.project_name = project_name

        if endpoint:
            self.endpoint = endpoint
        else:
            self.endpoint = EndpointConfig(constants.DEFAULT_SERVER_URL)

    def get_model(self, lang):
        return self.models.get(lang)

    def parse(self, text, lang):
        """Parse a text message.

        Return a default value if the parsing of the text failed."""

        default_return = {"intent": {"name": "", "confidence": 0.0},
                          "entities": [], "text": ""}
        result = self._rasa_http_parse(text, lang)

        return result if result is not None else default_return

    def _rasa_http_parse(self, text, lang):
        """Send a text message to a running rasa NLU http server.

        Return `None` on failure."""

        if not self.endpoint:
            logger.error(
                    "Failed to parse text '{}' using rasa NLU over http. "
                    "No rasa NLU server specified!".format(text))
            return None

        params = {
            "token": self.endpoint.token,
            "model": self.get_model(lang),
            "project": self.project_name,
            "q": text
        }
        url = "{}/parse".format(self.endpoint.url)
        try:
            result = requests.get(url, params=params)
            if result.status_code == 200:
                return result.json()
            else:
                logger.error(
                        "Failed to parse text '{}' using rasa NLU over http. "
                        "Error: {}".format(text, result.text))
                return None
        except Exception as e:
            logger.error(
                    "Failed to parse text '{}' using rasa NLU over http. "
                    "Error: {}".format(text, e))
            return None
