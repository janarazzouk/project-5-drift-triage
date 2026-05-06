from typing import Any

import httpx

from app.contracts.promotion import PromotionRequestPayload
from app.core.errors import ExternalServiceError


class ModelServiceClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def get_replay_comparison(self) -> dict[str, Any]:
        return self._get("/replay-fixture/compare")

    def get_promotion_checklist(self) -> dict[str, Any]:
        return self._get("/promotion/checklist")

    def request_production_promotion(
        self,
        payload: PromotionRequestPayload,
    ) -> dict[str, Any]:
        return self._post(
            "/promotion/production",
            payload.model_dump(mode="json"),
            headers={
                "X-Contract-Version": payload.contract_version,
                "X-Idempotency-Key": payload.request_id,
            },
        )

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Model service GET {path} failed: {exc}"
            ) from exc

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        request_headers = {
            "Content-Type": "application/json",
        }

        if headers:
            request_headers.update(headers)

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=request_headers,
                )

                if response.status_code == 409:
                    return response.json()

                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Model service POST {path} failed: {exc}"
            ) from exc