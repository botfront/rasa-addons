import time
import logging
import requests
from rasa.nlu.extractors.duckling_http_extractor import DucklingHTTPExtractor, convert_duckling_format_to_rasa
from rasa.utils.common import raise_warning
from rasa.nlu.training_data import Message

from typing import Any, List, Optional, Text, Dict
from rasa.constants import DOCS_URL_COMPONENTS
from rasa.nlu.constants import ENTITIES

logger = logging.getLogger(__name__)


class DucklingHTTPExtractorWithTimezone(DucklingHTTPExtractor):

    def _duckling_parse(self, text: Text, reference_time: int, timezone) -> List[Dict[Text, Any]]:
        """Sends the request to the duckling server and parses the result."""

        try:
            payload = self._payload(text, reference_time)
            payload["tz"] = timezone # mod
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            }
            response = requests.post(
                self._url() + "/parse",
                data=payload,
                headers=headers,
                timeout=self.component_config.get("timeout"),
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    "Failed to get a proper response from remote "
                    "duckling. Status Code: {}. Response: {}"
                    "".format(response.status_code, response.text)
                )
                return []
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            logger.error(
                "Failed to connect to duckling http server. Make sure "
                "the duckling server is running/healthy/not stale and the proper host "
                "and port are set in the configuration. More "
                "information on how to run the server can be found on "
                "github: "
                "https://github.com/facebook/duckling#quickstart "
                "Error: {}".format(e)
            )
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
                logging.warning(
                    "Could not parse timestamp {}. Instead "
                    "current UTC time will be passed to "
                    "duckling. Error: {}".format(message.time, e)
                )
        # fallbacks to current time, multiplied by 1000 because duckling
        # requires the reftime in milliseconds
        elif reference_time is not None:
            try:
                return int(reference_time)
            except ValueError as e:
                logging.warning(
                    "Could not parse timestamp {}. Instead "
                    "current UTC time will be passed to "
                    "duckling. Error: {}".format(reference_time, e)
                )
        return int(time.time()) * 1000

    def process(self, message: Message, **kwargs: Any) -> None:

        if self._url() is not None:
            # mod >
            params = kwargs
            timezone = self._timezone_from_config_or_request(
                self.component_config, params.get("timezone", None)
            )
            reference_time = self._reference_time_from_message_or_request(
                message, params.get("reference_time", None)
            )
            matches = self._duckling_parse(message.text, reference_time, timezone)
            # </ mod
            all_extracted = convert_duckling_format_to_rasa(matches)
            dimensions = self.component_config["dimensions"]
            extracted = DucklingHTTPExtractor.filter_irrelevant_entities(
                all_extracted, dimensions
            )
        else:
            extracted = []
            raise_warning(
                "Duckling HTTP component in pipeline, but no "
                "`url` configuration in the config "
                "file nor is `RASA_DUCKLING_HTTP_URL` "
                "set as an environment variable. No entities will be extracted!",
                docs=DOCS_URL_COMPONENTS + "#ducklinghttpextractor",
            )

        extracted = self.add_extractor_name(extracted)
        message.set(
            ENTITIES, message.get(ENTITIES, []) + extracted, add_to_output=True,
        )