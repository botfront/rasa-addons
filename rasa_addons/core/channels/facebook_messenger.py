from typing import Text, List, Dict, Any, Callable, Awaitable, Iterable, Optional
import hashlib
import hmac
import warnings
import logging
from fbmessenger import MessengerClient
from fbmessenger.attachments import Image
from fbmessenger.elements import Text as FBText
from fbmessenger.quick_replies import QuickReplies, QuickReply
from sanic import Blueprint, response
from sanic.request import Request
from typing import Text, List, Dict, Any, Callable, Awaitable, Iterable, Optional

from rasa.core.channels.channel import UserMessage, OutputChannel, InputChannel
from rasa.core.channels.facebook import Messenger, MessengerBot, FacebookInput
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)


class FBMessengerInput(FacebookInput):
    @classmethod
    def from_credentials(cls, credentials):
        if not credentials:
            cls.raise_missing_credentials_exception()

        return cls(
            credentials.get("verify"),
            credentials.get("secret"),
            credentials.get("page-access-token"),
            credentials.get("fields"),
        )

    def __init__(self, fb_verify, fb_secret, fb_access_token, fields) -> None:
        super().__init__(fb_verify, fb_secret, fb_access_token)
        self.fields = fields

    @staticmethod
    def get_language(user):
        if "locale" in user:
            split = user["locale"].split("_")
            if len(split) > 0:
                return split[0]
        return None

    def get_metadata(self, request: Request):
        messenger = Messenger(self.fb_access_token, None)
        sender_id = (
            request.json.get("entry")[0].get("messaging")[0].get("sender").get("id")
        )
        user = messenger.client.get_user_data(sender_id, fields=self.fields)
        return {"user": user, "language": self.get_language(user)}

