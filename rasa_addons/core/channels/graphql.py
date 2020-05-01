import logging
from typing import Text, Any, Dict, Optional, List

from rasa.core.constants import DEFAULT_REQUEST_TIMEOUT
from rasa.core.nlg.generator import NaturalLanguageGenerator
from rasa.core.trackers import DialogueStateTracker, EventVerbosity
from rasa.utils.endpoints import EndpointConfig
import os

logger = logging.getLogger(__name__)


CONFIG_QUERY = """
query(
    $projectId: String!, $environment: String
) {
    getConfig(
        projectId: $projectId,environment:$environment
    ) {
        credentials
        endpoints
    }
}
"""


async def get_config_via_graphql(bf_url, project_id):
    from sgqlc.endpoint.http import HTTPEndpoint

    logging.getLogger("sgqlc.endpoint.http").setLevel(logging.WARNING)
    import urllib.error

    environment = os.environ.get("BOTFRONT_ENV", "development")
    api_key = os.environ.get("API_KEY")
    headers = [{"Authorization": api_key}] if api_key else []
    endpoint = HTTPEndpoint(bf_url, *headers)

    async def load():
        try:
            logger.debug(f"fetching endpoints and credentials at {bf_url}")
            response = endpoint(
                CONFIG_QUERY, {"projectId": project_id, "environment": environment}
            )
            if "errors" in response and response["errors"]:
                raise urllib.error.URLError("Null response.")
            return endpoint(
                CONFIG_QUERY, {"projectId": project_id, "environment": environment}
            )["data"]
        except urllib.error.URLError:
            logger.debug(
                f"something went wrong at {bf_url} with the query {CONFIG_QUERY}"
            )
            return None

    data = await load()
    return data["getConfig"]
