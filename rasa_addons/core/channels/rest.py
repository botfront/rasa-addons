import asyncio
import rasa
import logging
import inspect
from rasa.core.channels.channel import RestInput, UserMessage, CollectingOutputChannel
from sanic.request import Request
from sanic import Sanic, Blueprint, response
from asyncio import Queue, CancelledError
from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable
from rasa.core import utils
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)

class BotfrontRestOutput(CollectingOutputChannel):
    @staticmethod
    def _message(
        recipient_id: Text,
        text: Text = None,
        image: Text = None,
        buttons: List[Dict[Text, Any]] = None,
        attachment: Text = None,
        custom: Dict[Text, Any] = None,
    ) -> Dict:
        """Create a message object that will be stored."""

        obj = {
            "recipient_id": recipient_id,
            "text": text,
            "image": image,
            "quick_replies": buttons, # compatibility with Rasa-webchat
            "attachment": attachment,
            "custom": custom,
        }

        # filter out any values that are `None`
        return utils.remove_none_values(obj)

class BotfrontRestInput(RestInput):
    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        return request.json.get("customData", {})

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
