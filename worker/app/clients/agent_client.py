from typing import Any

import httpx

from app.core.errors import ExternalServiceError
from app.schemas.job import JobResultPayload


class AgentClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        result_path: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.result_path = result_path

    def send_job_result(
        self,
        payload: JobResultPayload,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{self.result_path}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    json=payload.model_dump(mode="json"),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Failed to send job result to agent: {exc}"
            ) from exc