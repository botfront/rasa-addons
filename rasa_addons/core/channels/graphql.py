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
    $projectId: String!
) {
    getConfig(
        projectId: $projectId
    ) {
       credentials
       endpoints
    }
}
"""

async def get_config_via_graphql(bf_url, project_id):
    from sgqlc.endpoint.http import HTTPEndpoint
    import urllib.error

    endpoint = HTTPEndpoint(bf_url)

    async def load():
        try:
            logger.debug(f'fetching endpoints and credentials at {bf_url}')
            response = endpoint(CONFIG_QUERY, {"projectId": project_id})
            if "errors" in response and response["errors"]: raise urllib.error.URLError("Null response.")
            return endpoint(CONFIG_QUERY, {"projectId": project_id})["data"]
        except urllib.error.URLError:
            logger.debug(f'something went wrong at {bf_url} with the query {CONFIG_QUERY}')
            return None

    data = await load()
    return data["getConfig"]

