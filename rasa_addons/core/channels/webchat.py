import logging
import uuid
from sanic import Blueprint, response
from sanic.request import Request
from socketio import AsyncServer
from typing import Optional, Text, Any, List, Dict, Iterable

from rasa.core.channels.channel import InputChannel
from rasa.core.channels.channel import UserMessage, OutputChannel

logger = logging.getLogger(__name__)


class SocketBlueprint(Blueprint):
    def __init__(self, sio: AsyncServer, socketio_path, *args, **kwargs):
        self.sio = sio
        self.socketio_path = socketio_path
        super(SocketBlueprint, self).__init__(*args, **kwargs)

    def register(self, app, options):
        self.sio.attach(app, self.socketio_path)
        super(SocketBlueprint, self).register(app, options)


class WebchatOutput(OutputChannel):
    @classmethod
    def name(cls):
        return "webchat"

    def __init__(self, sio, sid, bot_message_evt):
        self.sio = sio
        self.sid = sid
        self.custom_data = None
        self.language = None
        self.bot_message_evt = bot_message_evt

    def set_custom_data(self, custom_data):
        self.custom_data = custom_data

    def set_language(self, language):
        self.language = language

    async def _send_message(self, socket_id: Text, response: Any) -> None:
        """Sends a message to the recipient using the bot event."""
        await self.sio.emit(self.bot_message_evt, response, room=socket_id)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""

        await self._send_message(self.sid, {"text": text})

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        """Sends an image to the output"""

        message = {"attachment": {"type": "image", "payload": {"src": image}}}
        await self._send_message(self.sid, message)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any
    ) -> None:
        """Sends buttons to the output."""

        message = {"text": text, "quick_replies": []}

        for button in buttons:
            message["quick_replies"].append(
                {
                    "type": button["type"],
                    "content_type": "text",
                    "title": button["title"],
                    "payload": button["payload"],
                }
            )

        await self._send_message(self.sid, message)

    async def send_elements(
            self, recipient_id: Text, elements: Iterable[Dict[Text, Any]], **kwargs: Any
    ) -> None:
        """Sends elements to the output."""

        message = {
            "attachment": {
                "type": "template",
                "payload": {"template_type": "generic", "elements": elements[0]},
            }
        }

        await self._send_message(self.sid, message)

    async def send_custom_json(
            self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends custom json to the output"""

        json_message.setdefault("room", self.sid)

        await self.sio.emit(self.bot_message_evt, **json_message)

    async def send_attachment(
        self, recipient_id: Text, attachment: Dict[Text, Any], **kwargs: Any
    ) -> None:
        """Sends an attachment to the user."""
        await self._send_message(self.sid, {"attachment": attachment})


class WebchatInput(InputChannel):
    """A socket.io input channel."""

    @classmethod
    def name(cls):
        return "webchat"

    @classmethod
    def from_credentials(cls, credentials):
        credentials = credentials or {}
        return cls(
            credentials.get("user_message_evt", "user_uttered"),
            credentials.get("bot_message_evt", "bot_uttered"),
            credentials.get("namespace"),
            credentials.get("session_persistence", False),
            credentials.get("socketio_path", "/socket.io"),
            credentials.get("cors_allowed_origins", "*")
        )

    def __init__(
        self,
        user_message_evt: Text = "user_uttered",
        bot_message_evt: Text = "bot_uttered",
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Text = "/socket.io",
        cors_allowed_origins = "*",
    ):
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.cors_allowed_origins = cors_allowed_origins

    def blueprint(self, on_new_message):
        # Workaround so that socketio works with requests from other origins.
        # https://github.com/miguelgrinberg/python-socketio/issues/205#issuecomment-493769183
        sio = AsyncServer(async_mode="sanic", cors_allowed_origins=self.cors_allowed_origins)
        socketio_webhook = SocketBlueprint(
            sio, self.socketio_path, "socketio_webhook", __name__
        )

        @socketio_webhook.route("/", methods=["GET"])
        async def health(request: Request):
            return response.json({"status": "ok"})

        @sio.on("connect", namespace=self.namespace)
        async def connect(sid, environ):
            logger.debug("User {} connected to socketIO endpoint.".format(sid))

        @sio.on("disconnect", namespace=self.namespace)
        async def disconnect(sid):
            logger.debug("User {} disconnected from socketIO endpoint.".format(sid))

        @sio.on("session_request", namespace=self.namespace)
        async def session_request(sid, data):
            if data is None:
                data = {}
            if "session_id" not in data or data["session_id"] is None:
                data["session_id"] = uuid.uuid4().hex
            await sio.emit("session_confirm", data["session_id"], room=sid)
            logger.debug("User {} connected to socketIO endpoint.".format(sid))

        @sio.on(self.user_message_evt, namespace=self.namespace)
        async def handle_message(sid, data):
            output_channel = WebchatOutput(sio, sid, self.bot_message_evt)

            if self.session_persistence:
                if not data.get("session_id"):
                    logger.warning(
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

            if "customData" in data:
                output_channel.set_custom_data(data["customData"])
                if "language" in data["customData"]:
                    output_channel.set_language(data["customData"]["language"])
            message = UserMessage(
                data["message"], output_channel, sender_id, input_channel=self.name()
            )
            await on_new_message(message)

        return socketio_webhook
