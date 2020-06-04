import logging

from sgqlc.endpoint.http import HTTPEndpoint
import urllib.error
import os

logger = logging.getLogger(__name__)
logging.getLogger("sgqlc.endpoint.http").setLevel(logging.WARNING)

SUBMIT_FORM = """
mutation(
    $projectId: String!, $environment: String, $tracker: Any!, $metadata: Any!
) {
    submitForm(
        projectId: $projectId, environment: $environment, tracker: $tracker, metadata: $metadata,
    ) {
        success
    }
}
"""


def submit_form_to_botfront(tracker,) -> None:
    environment = os.environ.get("BOTFRONT_ENV", "development")
    project_id = os.environ.get("BF_PROJECT_ID")
    bf_url = os.environ.get("BF_URL", "server")
    api_key = os.environ.get("API_KEY")
    headers = [{"Authorization": api_key}] if api_key else []
    endpoint = HTTPEndpoint(bf_url, *headers)

    try:
        response = endpoint(
            SUBMIT_FORM,
            {
                "projectId": project_id,
                "environment": environment,
                "tracker": tracker.current_state(),
                "metadata": tracker.latest_message.metadata,
            },
        )
        if response.get("errors") or not response.get("data", {}).get(
            "submitForm", {}
        ).get("success", False):
            errors = ", ".join([e.get("message") for e in response.get("errors", [])])
            raise urllib.error.URLError(errors)
    except urllib.error.URLError as e:
        logger.error(f"Could not submit form information to {bf_url}. " + e.reason)
