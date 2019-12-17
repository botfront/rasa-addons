import asyncio
import rasa
import logging
import json
import inspect
from rasa.core.channels.channel import RestInput
from sanic.request import Request
from sanic import Sanic, Blueprint, response
from asyncio import Queue, CancelledError
from typing import Text, List, Dict, Any, Optional, Callable, Iterable, Awaitable
from rasa.core import utils

logger = logging.getLogger(__name__)

class BotfrontRestInput(RestInput):
    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        return request.json.get("customData", {})
