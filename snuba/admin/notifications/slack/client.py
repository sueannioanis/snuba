import logging
from typing import Any, MutableMapping, Optional

import requests

from snuba import settings

logger = logging.getLogger("snuba.admin.notifications.slack")


class SlackClient(object):
    @property
    def token(self) -> Optional[str]:
        return settings.SLACK_API_TOKEN

    def post_message(
        self, message: MutableMapping[str, Any], channel: Optional[str] = None
    ) -> None:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        if channel:
            message["channel"] = channel

        try:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage", headers=headers, json=message,
            )
        except Exception as exc:
            logger.error(exc, exc_info=True)

            # Slack error handling
            # Copied from https://github.com/getsentry/sentry/blob/601f829c9246ae73c8169510140fd7f47fc6dfc3/src/sentry/integrations/slack/client.py#L36-L53
        content_type = resp.headers["content-type"]
        if content_type == "text/html":
            is_ok = str(resp.content) == "ok"
            # If there is an error, Slack just makes the error the entire response.
            error_option = resp.content

        else:
            # The content-type should be "application/json" at this point but we don't check.
            response = resp.json()
            is_ok = response.get("ok")
            error_option = response.get("error")

        if not is_ok:
            logger.error(f"Slack error: {str(error_option)}")
