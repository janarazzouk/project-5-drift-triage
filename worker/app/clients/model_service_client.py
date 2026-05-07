from typing import Any

import httpx

from app.core.errors import ExternalServiceError


class ModelServiceClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        rollback_path: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.rollback_path = rollback_path

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def get_replay_comparison(self) -> dict[str, Any]:
        return self._get("/replay-fixture/compare")

    def request_rollback(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(
            self.rollback_path,
            payload,
        )

    def _get(
        self,
        path: str,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code in {409, 422}:
                    return response.json()

                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"Model service POST {path} failed: {exc}"
            ) from exc