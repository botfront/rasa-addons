import time

import logging
import os
import requests
import simplejson
from typing import Any, List, Optional, Text, Dict

from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.extractors import EntityExtractor
from rasa.nlu.model import Metadata
from rasa.nlu.training_data import Message

logger = logging.getLogger(__name__)


def extract_value(match):
    if match["value"].get("type") == "interval":
        value = {"to": match["value"].get("to", {}).get("value"),
                 "from": match["value"].get("from", {}).get("value")}
    else:
        value = match["value"].get("value")

    return value


def filter_irrelevant_matches(matches, requested_dimensions):
    """Only return dimensions the user configured"""

    if requested_dimensions:
        return [match
                for match in matches
                if match["dim"] in requested_dimensions]
    else:
        return matches


def convert_duckling_format_to_rasa(matches):
    extracted = []

    for match in matches:
        value = extract_value(match)
        entity = {"start": match["start"],
                  "end": match["end"],
                  "text": match.get("body", match.get("text", None)),
                  "value": value,
                  "confidence": 1.0,
                  "additional_info": match["value"],
                  "entity": match["dim"]}

        extracted.append(entity)

    return extracted


class DucklingHTTPExtractor(EntityExtractor):
    """Searches for structured entites, e.g. dates, using a duckling server."""

    name = "DucklingHTTPExtractor"

    provides = ["entities"]

    defaults = {
        # by default all dimensions recognized by duckling are returned
        # dimensions can be configured to contain an array of strings
        # with the names of the dimensions to filter for
        "dimensions": None,

        # http url of the running duckling server
        "url": None,

        # locale - if not set, we will use the language of the model
        "locale": None,

        # timezone like Europe/Berlin
        # if not set the default timezone of Duckling is going to be used
        "timezone": None
    }

    def __init__(self,
                 component_config: Text = None,
                 language: Optional[List[Text]] = None) -> None:

        super(DucklingHTTPExtractor, self).__init__(component_config)
        self.language = language

    @classmethod
    def create(
        cls, component_config: Dict[Text, Any], config: RasaNLUModelConfig
    ) -> 'DucklingHTTPExtractor':
        return cls(component_config,
                   config.language)

    def _locale(self):
        if not self.component_config.get("locale"):
            # this is king of a quick fix to generate a proper locale
            # works most of the time
            locale_fix = "{}_{}".format(self.language, self.language.upper())
            self.component_config["locale"] = locale_fix
        return self.component_config.get("locale")

    def _url(self):
        """Return url of the duckling service. Environment var will override."""
        if os.environ.get("RASA_DUCKLING_HTTP_URL"):
            return os.environ["RASA_DUCKLING_HTTP_URL"]

        return self.component_config.get("url")

    def _payload(self, text, reference_time, timezone):
        return {
            "text": text,
            "locale": self._locale(),
            "tz": timezone,
            "reftime": reference_time
        }

    def _duckling_parse(self, text, reference_time, timezone):
        """Sends the request to the duckling server and parses the result."""

        try:
            payload = self._payload(text, reference_time, timezone)
            headers = {"Content-Type": "application/x-www-form-urlencoded; "
                                       "charset=UTF-8"}
            response = requests.post(self._url() + "/parse",
                                     data=payload,
                                     headers=headers)
            if response.status_code == 200:
                return simplejson.loads(response.text)
            else:
                logger.error("Failed to get a proper response from remote "
                             "duckling. Status Code: {}. Response: {}"
                             "".format(response.status_code, response.text))
                return []
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to duckling http server. Make sure "
                         "the duckling server is running and the proper host "
                         "and port are set in the configuration. More "
                         "information on how to run the server can be found on "
                         "github: "
                         "https://github.com/facebook/duckling#quickstart "
                         "Error: {}".format(e))
            return []

    @staticmethod
    def _timezone_from_config_or_request(component_config, timezone):
        if timezone is not None:
            return timezone
        return component_config.get("timezone")

    @staticmethod
    def _reference_time_from_message_or_request(message, reference_time):
        if message.time is not None:
            try:
                return int(message.time) * 1000
            except ValueError as e:
                logging.warning("Could not parse timestamp {}. Instead "
                                "current UTC time will be passed to "
                                "duckling. Error: {}".format(message.time, e))
        # fallbacks to current time, multiplied by 1000 because duckling
        # requires the reftime in milliseconds
        elif reference_time is not None:
            try:
                return int(reference_time)
            except ValueError as e:
                logging.warning("Could not parse timestamp {}. Instead "
                                "current UTC time will be passed to "
                                "duckling. Error: {}".format(reference_time, e))
        return int(time.time()) * 1000

    def process(self, message: Message, **kwargs: Any) -> None:

        if self._url() is not None:
            params = kwargs
            timezone = self._timezone_from_config_or_request(
                self.component_config, params.get("timezone", None))
            reference_time = self._reference_time_from_message_or_request(
                message, params.get("reference_time", None))
            matches = self._duckling_parse(message.text, reference_time,
                                           timezone)
            dimensions = self.component_config["dimensions"]
            relevant_matches = filter_irrelevant_matches(matches, dimensions)
            extracted = convert_duckling_format_to_rasa(relevant_matches)
        else:
            extracted = []
            logger.warning("Duckling HTTP component in pipeline, but no "
                           "`url` configuration in the config "
                           "file nor is `RASA_DUCKLING_HTTP_URL` "
                           "set as an environment variable.")

        extracted = self.add_extractor_name(extracted)
        message.set("entities",
                    message.get("entities", []) + extracted,
                    add_to_output=True)

    @classmethod
    def load(cls,
             component_meta: Dict[Text, Any],
             model_dir: Text = None,
             model_metadata: Metadata = None,
             cached_component: Optional['DucklingHTTPExtractor'] = None,
             **kwargs: Any
             ) -> 'DucklingHTTPExtractor':
        return cls(component_meta, model_metadata.get("language"))
