import logging
import warnings
import uuid
from sanic import Sanic, Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from socketio import AsyncServer

from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable

from rasa.core.channels.channel import UserMessage, InputChannel
from rasa.core.channels.socketio import SocketIOInput, SocketIOOutput, SocketBlueprint

logger = logging.getLogger(__name__)


class WebchatOutput(SocketIOOutput):
    @classmethod
    def name(cls):
        return "webchat"

    async def _send_message(self, socket_id: Text, response: Any) -> None:
        """Sends a message to the recipient using the bot event."""

        await self.sio.emit(self.bot_message_evt, response, room=socket_id)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""

        message_parts = text.split("\n\n")
        for i in range(len(message_parts)):
            text_message = {"text": message_parts[i]}
            if i == len(message_parts) - 1:
                text_message["metadata"] = kwargs.get("metadata", {})
            await self._send_message(self.sid, text_message)

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        """Sends an image to the output"""

        message = {
            "attachment": {"type": "image", "payload": {"src": image}},
            "metadata": kwargs.get("metadata", {}),
        }
        await self._send_message(self.sid, message)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        """Sends buttons to the output."""

        message = {
            "text": text,
            "quick_replies": [],
            "quick_replies": buttons,
            "metadata": kwargs.get("metadata", {}),
        }

        await self._send_message(self.sid, message)

    async def send_elements(
        self, recipient_id: Text, elements: Iterable[Dict[Text, Any]], **kwargs: Any
    ) -> None:
        """Sends elements to the output."""

        for element in elements:
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": element},
                },
                "metadata": kwargs.get("metadata", {}),
            }

            await self._send_message(self.sid, message)

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends custom json to the output"""

        json_message.setdefault("room", self.sid)

        await self.sio.emit(
            self.bot_message_evt, **json_message, metadata=kwargs.get("metadata", {})
        )

    async def send_attachment(
        self, recipient_id: Text, attachment: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends an attachment to the user."""
        await self._send_message(
            self.sid, {"attachment": attachment, "metadata": kwargs.get("metadata", {})}
        )


class WebchatInput(SocketIOInput):
    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        return cls(
            credentials.get("user_message_evt", "user_uttered"),
            credentials.get("bot_message_evt", "bot_uttered"),
            credentials.get("namespace"),
            credentials.get("session_persistence", False),
            credentials.get("socketio_path", "/socket.io"),
            credentials.get("cors_allowed_origins", "*"),
        )

    @classmethod
    def name(cls):
        return "webchat"

    def __init__(
        self,
        user_message_evt: Text = "user_uttered",
        bot_message_evt: Text = "bot_uttered",
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Optional[Text] = "/socket.io",
        cors_allowed_origins="*",
    ):
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.cors_allowed_origins = cors_allowed_origins

    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        return request.get("customData", {})

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        # Workaround so that socketio works with requests from other origins.
        # https://github.com/miguelgrinberg/python-socketio/issues/205#issuecomment-493769183
        sio = AsyncServer(
            async_mode="sanic", cors_allowed_origins=self.cors_allowed_origins
        )
        socketio_webhook = SocketBlueprint(
            sio, self.socketio_path, "socketio_webhook", __name__
        )

        @socketio_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @sio.on("connect", namespace=self.namespace)
        async def connect(sid: Text, _) -> None:
            logger.debug(f"User {sid} connected to socketIO endpoint.")

        @sio.on("disconnect", namespace=self.namespace)
        async def disconnect(sid: Text) -> None:
            logger.debug(f"User {sid} disconnected from socketIO endpoint.")

        @sio.on("session_request", namespace=self.namespace)
        async def session_request(sid: Text, data: Optional[Dict]):
            if data is None:
                data = {}
            if "session_id" not in data or data["session_id"] is None:
                data["session_id"] = uuid.uuid4().hex
            await sio.emit("session_confirm", data["session_id"], room=sid)
            logger.debug(f"User {sid} connected to socketIO endpoint.")

        @sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_message(sid: Text, data: Dict) -> Any:
            output_channel = WebchatOutput(sio, sid, self.bot_message_evt)

            if self.session_persistence:
                if not data.get("session_id"):
                    warnings.warn(
                        "A message without a valid sender_id "
                        "was received. This message will be "
                        "ignored. Make sure to set a proper "
                        "session id using the "
                        "`session_request` socketIO event."
                    )
                    return
                sender_id = data["session_id"]
            else:
                sender_id = sid

            message = UserMessage(
                data["message"],
                output_channel,
                sender_id,
                input_channel=self.name(),
                metadata=self.get_metadata(data),
            )
            await on_new_message(message)

        return socketio_webhook
