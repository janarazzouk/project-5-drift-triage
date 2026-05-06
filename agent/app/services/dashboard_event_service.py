from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class DashboardEventService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def emit_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.settings.dashboard_url:
            logger.info(
                "Dashboard URL is not configured. Event stored only in database.",
                extra={"event_type": event_type},
            )
            return

        url = f"{self.settings.dashboard_url.rstrip('/')}/events"

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    url,
                    json={
                        "event_type": event_type,
                        "payload": payload,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "Failed to emit dashboard event.",
                extra={
                    "event_type": event_type,
                    "error": str(exc),
                },
            )