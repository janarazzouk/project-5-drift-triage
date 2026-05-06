import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.drift_webhook import DriftWebhookPayload


logger = logging.getLogger(__name__)


class AgentWebhookService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_drift_severity_changed(
        self,
        payload: DriftWebhookPayload,
    ) -> dict[str, Any] | None:
        if not self.settings.agent_drift_webhook_url:
            logger.info(
                "Skipping drift webhook because MODEL_SERVICE_AGENT_DRIFT_WEBHOOK_URL is not set."
            )
            return None

        payload_data = payload.model_dump(mode="json")

        headers = {
            "Content-Type": "application/json",
            "X-Contract-Version": payload.contract_version,
            "X-Idempotency-Key": payload.event_id,
        }

        try:
            response = httpx.post(
                self.settings.agent_drift_webhook_url,
                json=payload_data,
                headers=headers,
                timeout=self.settings.agent_webhook_timeout_seconds,
            )
            response.raise_for_status()

            if response.content:
                return response.json()

            return {"accepted": True}

        except httpx.HTTPError as exc:
            logger.warning(
                "Failed to send drift webhook to agent. The drift result was still saved. Error: %s",
                exc,
            )
            return None