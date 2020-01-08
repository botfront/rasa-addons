import logging
from typing import Text, Any, Dict, Optional, List

from rasa.core.constants import DEFAULT_REQUEST_TIMEOUT
from rasa.core.nlg.generator import NaturalLanguageGenerator
from rasa.core.trackers import DialogueStateTracker, EventVerbosity
from rasa.utils.endpoints import EndpointConfig
import os

logger = logging.getLogger(__name__)


NLG_QUERY = """
query(
    $template: StringOrListOfStrings!
    $arguments: Any
    $tracker: ConversationInput
    $channel: NlgRequestChannel
) {
    getResponse(
        template: $template
        arguments: $arguments
        tracker: $tracker
        channel: $channel
    ) {
        text
        metadata
        ...on QuickReplyPayload { buttons { title, type, ...on WebUrlButton { url } ...on PostbackButton { payload } } }
        ...on ImagePayload { image }
        ...on CustomPayload { buttons { title, type, ...on WebUrlButton { url } ...on PostbackButton { payload } }, elements, attachment, image, custom }
    }
}
"""


def nlg_response_format_spec():
    """Expected response schema for an NLG endpoint.

    Used for validation of the response returned from the NLG endpoint."""
    return {
        "type": "object",
        "properties": {
            "text": {"type": ["string", "null"]},
            "buttons": {"type": ["array", "null"], "items": {"type": "object"}},
            "elements": {"type": ["array", "null"], "items": {"type": "object"}},
            "attachment": {"type": ["object", "null"]},
            "image": {"type": ["string", "null"]},
        },
    }


def nlg_request_format_spec():
    """Expected request schema for requests sent to an NLG endpoint."""

    return {
        "type": "object",
        "properties": {
            "template": {"type": "string"},
            "arguments": {"type": "object"},
            "tracker": {
                "type": "object",
                "properties": {
                    "sender_id": {"type": "string"},
                    "slots": {"type": "object"},
                    "latest_message": {"type": "object"},
                    "latest_event_time": {"type": "number"},
                    "paused": {"type": "boolean"},
                    "events": {"type": "array"},
                },
            },
            "channel": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
    }


def nlg_request_format(
    template_name: Text,
    tracker: DialogueStateTracker,
    output_channel: Text,
    **kwargs: Any,
) -> Dict[Text, Any]:
    """Create the json body for the NLG json body for the request."""

    tracker_state = tracker.current_state(EventVerbosity.ALL)

    return {
        "template": template_name,
        "arguments": kwargs,
        "tracker": tracker_state,
        "channel": {"name": output_channel},
    }


class GraphQLNaturalLanguageGenerator(NaturalLanguageGenerator):
    """Like Rasa's CallbackNLG, but queries Botfront's GraphQL endpoint"""

    def __init__(self, **kwargs) -> None:
        endpoint_config = kwargs.get("endpoint_config")
        self.nlg_endpoint = endpoint_config

    async def generate(
        self,
        template_name: Text,
        tracker: DialogueStateTracker,
        output_channel: Text,
        **kwargs: Any,
    ) -> List[Dict[Text, Any]]:

        fallback_language_slot = tracker.slots.get("fallback_language")
        fallback_language = fallback_language_slot.initial_value if fallback_language_slot else None
        language = tracker.latest_message.metadata.get("language") or fallback_language

        body = nlg_request_format(
            template_name,
            tracker,
            output_channel,
            **kwargs,
            language=language,
            projectId=os.environ.get("BF_PROJECT_ID"),
        )

        logger.debug(
            "Requesting NLG for {} from {}."
            "".format(template_name, self.nlg_endpoint.url)
        )

        try:
            if "graphql" in self.nlg_endpoint.url:
                from sgqlc.endpoint.http import HTTPEndpoint

                response = HTTPEndpoint(self.nlg_endpoint.url)(NLG_QUERY, body)
                response = response["data"]["getResponse"]
            else:
                response = await self.nlg_endpoint.request(
                    method="post", json=body, timeout=DEFAULT_REQUEST_TIMEOUT
                )
                response = response[0]  # legacy route, use first message in seq
        except Exception as e:
            logger.error("NLG web endpoint returned an invalid response: {}".format(e))
            return {"text": template_name}

        if self.validate_response(response):
            return response
        else:
            logger.error("NLG web endpoint returned an invalid response.")
            return {"text": template_name}

    @staticmethod
    def validate_response(content: Optional[Dict[Text, Any]]) -> bool:
        """Validate the NLG response. Raises exception on failure."""

        from jsonschema import validate
        from jsonschema import ValidationError

        try:
            if content is None or content == "":
                # means the endpoint did not want to respond with anything
                return True
            else:
                validate(content, nlg_response_format_spec())
                return True
        except ValidationError as e:
            e.message += (
                ". Failed to validate NLG response from API, make sure your "
                "response from the NLG endpoint is valid. "
                "For more information about the format please consult the "
                "`nlg_response_format_spec` function from this same module: "
                "https://github.com/RasaHQ/rasa/blob/master/rasa/core/nlg/callback.py#L12"
            )
            raise e
