import logging
import warnings
import uuid
from sanic import Sanic, Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from socketio import AsyncServer
import os


from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable

from rasa.core.channels.channel import UserMessage
from rasa.core.channels.socketio import SocketIOInput, SocketIOOutput, SocketBlueprint

from rasa.core.channels.channel import InputChannel
from rasa_addons.core.channels.webchat import WebchatOutput
from rasa_addons.core.channels.webchat import WebchatInput
from rasa_addons.core.channels.graphql import get_config_via_graphql

logger = logging.getLogger(__name__)


class WebchatPlusInput(WebchatInput):
    @classmethod
    def name(cls):
        return "webchat"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        credentials = credentials or {}
        return cls(
            credentials.get("user_message_evt", "user_uttered"),
            credentials.get("bot_message_evt", "bot_uttered"),
            credentials.get("namespace"),
            credentials.get("session_persistence", False),
            credentials.get("socketio_path", "/socket.io"),
            credentials.get("cors_allowed_origins","*"),
            credentials.get("config"),
        )

    def __init__(
        self,
        user_message_evt: Text = "user_uttered",
        bot_message_evt: Text = "bot_uttered",
        namespace: Optional[Text] = None,
        session_persistence: bool = False,
        socketio_path: Optional[Text] = "/socket.io",
        cors_allowed_origins="*",
        config = None
    ):
        self.bot_message_evt = bot_message_evt
        self.session_persistence = session_persistence
        self.user_message_evt = user_message_evt
        self.namespace = namespace
        self.socketio_path = socketio_path
        self.cors_allowed_origins = cors_allowed_origins
        self.config = config
       

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
                
            if self.config is not None:
                props = self.config
            else:
                config = await get_config_via_graphql(os.environ['BF_URL'], os.environ['BF_PROJECT_ID'])
                props = config['credentials']['rasa_addons.core.channels.webchat_plus.WebchatPlusInput']['props']
           
            await sio.emit("session_confirm", {
                'session_id':data["session_id"], 'props': props
                }, room=sid)
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


