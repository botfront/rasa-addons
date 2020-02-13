from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import requests
import logging
import json

from typing import Any

from rasa.nlu.components import Component
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.training_data.message import Message

logger = logging.getLogger(__name__)


class BingSpellCheck(Component):
    name = "BingSpellCheck"

    defaults = {"key": "", "min_score": 0.8, "language": "en-US", "enabled": True}

    def __init__(self, component_config=None):
        # type: (RasaNLUModelConfig) -> None
        super(BingSpellCheck, self).__init__(component_config)

        self.url = "https://api.cognitive.microsoft.com/bing/v7.0/spellcheck/"
        self.header = {
            "Ocp-Apim-Subscription-Key": self.component_config["key"],
            "setLang": self.component_config["language"][:2],
        }

    def process(self, message, **kwargs):
        # type: (Message, **Any) -> None

        text = message.text
        response = self._response(text)
        tokens = response.get("flaggedTokens", [])

        replacements = self._get_replacements(tokens)

        if self.component_config.get("enabled", True):
            message.text = self._replace(text, replacements)

    def _response(self, text):
        # type (str) -> dict
        default_response = {"_type": "SpellCheck", "flaggedTokens": []}

        try:
            response = requests.post(
                self.url, data=self._payload(text), headers=self.header
            )
            if response.status_code == 200:
                return json.loads(response.text)
            else:
                logger.error(
                    "Failed to get a proper response from spell check "
                    "server {}. Status Code: {}. Response: {}"
                    "".format(self.url, response.status_code, response.text)
                )

                return default_response
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "Failed to connect to the spell check http server. "
                "More information at "
                "https://azure.microsoft.com/en-us/services/cognitive-services/spell-check/"
                "Error: {}".format(e)
            )
            return default_response

    def _payload(self, text):
        return {"text": text, "mode": "spell", "mkt": self.component_config["language"]}

    @staticmethod
    def _replace(text, replacements):
        replacements.sort(key=lambda x: x["offset"])
        start_next = len(text)

        while len(replacements):
            flagged_token = replacements.pop()

            offset = flagged_token["offset"]
            token = flagged_token["token"]
            replacement = flagged_token["replacement"]

            if offset + len(token) <= start_next:
                text = text[0:offset] + replacement + text[offset + len(token) :]
                start_next = offset

        return text

    def _get_replacements(self, tokens):
        replacements = []
        for flagged_token in tokens:

            offset = flagged_token["offset"]
            token = flagged_token["token"]
            suggestions = sorted(
                flagged_token["suggestions"], key=lambda x: x["score"], reverse=True
            )

            if (
                len(suggestions)
                and suggestions[0]["score"] > self.component_config["min_score"]
            ):
                replacements.append(
                    {
                        "offset": offset,
                        "token": token,
                        "replacement": suggestions[0]["suggestion"],
                    }
                )

        return replacements
