import asyncio
import rasa
import logging
import json
import inspect
from rasa.core.channels.channel import InputChannel, OutputChannel, UserMessage, QueueOutputChannel
from sanic.request import Request
from sanic import Sanic, Blueprint, response
from asyncio import Queue, CancelledError
from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable
from rasa.core import utils

logger = logging.getLogger(__name__)

class RestOutput(OutputChannel):
    def __init__(self):
        self.messages = []
        self.custom_data = None
        self.language = None
    
    def set_custom_data(self, custom_data):
        self.custom_data = custom_data

    def set_language(self, language):
        self.language = language

    @classmethod
    def name(cls):
        return "rest"

    @staticmethod
    def _message(
        recipient_id, text=None, image=None, buttons=None, attachment=None, custom=None, metadata=None
    ):
        """Create a message object that will be stored."""

        obj = {
            "recipient_id": recipient_id,
            "text": text,
            "image": image,
            "quick_replies": buttons,
            "attachment": attachment,
            "custom": custom,
            "metadata": metadata,
        }

        # filter out any values that are `None`
        return utils.remove_none_values(obj)

    def latest_output(self):
        if self.messages:
            return self.messages[-1]
        else:
            return None

    async def _persist_message(self, message) -> None:
        self.messages.append(message)  # pytype: disable=bad-return-type

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        for message_part in text.split("\n\n"):
            if 'metadata' in kwargs.keys():
                await self._persist_message(self._message(recipient_id, text=message_part, metadata=kwargs["metadata"]))
            else:
                await self._persist_message(self._message(recipient_id, text=message_part))

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        """Sends an image. Default will just post the url as a string."""

        await self._persist_message(self._message(recipient_id, image=image))

    async def send_attachment(
        self, recipient_id: Text, attachment: Text, **kwargs: Any
    ) -> None:
        """Sends an attachment. Default will just post as a string."""

        await self._persist_message(self._message(recipient_id, attachment=attachment))

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any
    ) -> None:
        if 'metadata' in kwargs.keys():
            await self._persist_message(
                self._message(recipient_id, text=text, buttons=buttons, metadata=kwargs["metadata"])
            )
        else:
            await self._persist_message(
                self._message(recipient_id, text=text, buttons=buttons)
            )

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        await self._persist_message(self._message(recipient_id, custom=json_message))

class RestInput(InputChannel):
    @classmethod
    def name(cls):
        return "rest"

    @staticmethod
    async def on_message_wrapper(
        on_new_message: Callable[[UserMessage], Awaitable[None]],
        text: Text,
        queue: Queue,
        sender_id: Text,
        input_channel: Text,
    ) -> None:
        collector = QueueOutputChannel(queue)

        message = UserMessage(text, collector, sender_id, input_channel=input_channel)
        await on_new_message(message)

        await queue.put("DONE")  # pytype: disable=bad-return-type

    async def _extract_sender(self, req: Request) -> Optional[Text]:
        return req.json.get("sender", None)

    # noinspection PyMethodMayBeStatic
    def _extract_message(self, req: Request) -> Optional[Text]:
        return req.json.get("message", None)

    def _extract_input_channel(self, req: Request) -> Text:
        return req.json.get("input_channel") or self.name()

    def _extract_custom_data(self, req: Request) -> Text:
        return req.json.get("customData", None)

    def stream_response(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[None]],
        text: Text,
        sender_id: Text,
        input_channel: Text,
    ) -> Callable[[Any], Awaitable[None]]:
        async def stream(resp: Any) -> None:
            q = Queue()
            task = asyncio.ensure_future(
                self.on_message_wrapper(
                    on_new_message, text, q, sender_id, input_channel
                )
            )
            result = None  # declare variable up front to avoid pytype error
            while True:
                result = await q.get()
                if result == "DONE":
                    break
                else:
                    await resp.write(json.dumps(result) + "\n")
            await task

        return stream  # pytype: disable=bad-return-type

    def blueprint(self, on_new_message: Callable[[UserMessage], Awaitable[None]]):
        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        # noinspection PyUnusedLocal
        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request):
            return response.json({"status": "ok"})

        @custom_webhook.route("/", methods=["POST"])
        async def receive(request: Request):
            sender_id = await self._extract_sender(request)
            text = self._extract_message(request)
            custom_data = self._extract_custom_data(request)
            should_use_stream = rasa.utils.endpoints.bool_arg(
                request, "stream", default=False
            )
            input_channel = self._extract_input_channel(request)

            output_channel = RestOutput()
            if custom_data:
                output_channel.set_custom_data(custom_data)
                if "language" in custom_data:
                    output_channel.set_language(custom_data["language"])
            if should_use_stream:
                return response.stream(
                    self.stream_response(
                        on_new_message, text, sender_id, input_channel
                    ),
                    content_type="text/event-stream",
                )
            else:
                # noinspection PyBroadException
                try:
                    await on_new_message(
                        UserMessage(
                            text, output_channel, sender_id, input_channel=input_channel
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
                return response.json(output_channel.messages)

        return custom_webhook
