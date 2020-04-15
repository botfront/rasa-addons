import asyncio
import rasa
import logging
import inspect
import os
from rasa.core.channels.channel import (
    RestInput,
    UserMessage,
    CollectingOutputChannel,
    InputChannel,
)
from sanic.request import Request
from sanic import Sanic, Blueprint, response
from asyncio import Queue, CancelledError
from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable
from rasa.core import utils
from sanic.response import HTTPResponse
from rasa_addons.core.channels.rest import BotfrontRestInput, BotfrontRestOutput
from rasa.utils.endpoints import EndpointConfig
from rasa_addons.core.channels.graphql import get_config_via_graphql

logger = logging.getLogger(__name__)


class BotfrontRestPlusInput(BotfrontRestInput):
    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        return cls(**credentials)

    def __init__(self, config: Optional[Dict[Text, Any]] = None):
        self.config = config

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:
        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        # noinspection PyUnusedLocal
        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @custom_webhook.route("/props", methods=["GET"])
        async def serve_rules(request: Request) -> HTTPResponse:
            if self.config:
                return response.json(self.config)
            else:
                config = await get_config_via_graphql(
                    os.environ["BF_URL"], os.environ["BF_PROJECT_ID"]
                )
                return config["credentials"]["rasa_addons.core.channels.rest_plus.BotfrontRestPlusInput"]


        @custom_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:
            sender_id = await self._extract_sender(request)
            text = self._extract_message(request)
            should_use_stream = rasa.utils.endpoints.bool_arg(
                request, "stream", default=False
            )
            input_channel = self._extract_input_channel(request)
            metadata = self.get_metadata(request)

            if should_use_stream:
                return response.stream(
                    self.stream_response(
                        on_new_message, text, sender_id, input_channel, metadata
                    ),
                    content_type="text/event-stream",
                )
            else:
                collector = BotfrontRestOutput()
                # noinspection PyBroadException
                try:
                    await on_new_message(
                        UserMessage(
                            text,
                            collector,
                            sender_id,
                            input_channel=input_channel,
                            metadata=metadata,
                        )
                    )
                except CancelledError:
                    logger.error(
                        "Message handling timed out for "
                        "user message '{}'.".format(text)
                    )
                except Exception:
                    logger.exception(
                        "An exception occured while handling "
                        "user message '{}'.".format(text)
                    )
                return response.json(collector.messages)

        return custom_webhook
