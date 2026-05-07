from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from ui.config import DashboardConfig


@dataclass
class ApiResult:
    ok: bool
    data: Any = None
    status_code: int | None = None
    error: str | None = None


class ApiClient:
    def __init__(self, config: DashboardConfig):
        self.config = config
        self.session = requests.Session()

    def _request(
        self,
        *,
        method: str,
        base_url: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResult:
        url = f"{base_url}{path}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_body,
                headers=headers,
                params=params,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.RequestException as exc:
            return ApiResult(
                ok=False,
                status_code=None,
                error=f"Could not reach {url}: {exc}",
            )

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = response.text

        if response.status_code >= 400:
            return ApiResult(
                ok=False,
                data=data,
                status_code=response.status_code,
                error=f"{method} {url} failed with status {response.status_code}",
            )

        return ApiResult(
            ok=True,
            data=data,
            status_code=response.status_code,
        )

    def get_agent(self, path: str, params: dict[str, Any] | None = None) -> ApiResult:
        return self._request(
            method="GET",
            base_url=self.config.agent_api_url,
            path=path,
            params=params,
        )

    def post_agent(
        self,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiResult:
        return self._request(
            method="POST",
            base_url=self.config.agent_api_url,
            path=path,
            json_body=body,
            headers=headers,
        )

    def get_model_service(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> ApiResult:
        return self._request(
            method="GET",
            base_url=self.config.model_service_api_url,
            path=path,
            params=params,
        )

    def post_model_service(
        self,
        path: str,
        body: dict[str, Any],
    ) -> ApiResult:
        return self._request(
            method="POST",
            base_url=self.config.model_service_api_url,
            path=path,
            json_body=body,
        )

    def health_agent(self) -> ApiResult:
        return self.get_agent("/health")

    def health_model_service(self) -> ApiResult:
        return self.get_model_service("/health")

    def get_queue_status(self) -> ApiResult:
        return self.get_agent("/queue/status")

    def get_pending_approvals(self) -> ApiResult:
        return self.get_agent("/approvals/pending")

    def get_all_approvals(self) -> ApiResult:
        return self.get_agent("/approvals", params={"limit": 100})

    def approve(self, approval_id: str, approved_by: str, note: str) -> ApiResult:
        return self.post_agent(
            f"/approvals/{approval_id}/approve",
            {
                "approved_by": approved_by,
                "note": note,
            },
        )

    def reject(self, approval_id: str, rejected_by: str, rejection_reason: str) -> ApiResult:
        return self.post_agent(
            f"/approvals/{approval_id}/reject",
            {
                "rejected_by": rejected_by,
                "rejection_reason": rejection_reason,
            },
        )

    def list_investigations(self) -> ApiResult:
        return self.get_agent("/investigations", params={"limit": 100})

    def get_investigation(self, investigation_id: str) -> ApiResult:
        return self.get_agent(f"/investigations/{investigation_id}")

    def get_investigation_summary(self, investigation_id: str) -> ApiResult:
        return self.get_agent(f"/investigations/{investigation_id}/summary")

    def get_registry(self) -> ApiResult:
        return self.get_model_service("/registry")

    def get_promotion_checklist(self) -> ApiResult:
        return self.get_model_service("/promotion/checklist")

    def get_latest_drift(self) -> ApiResult:
        result = self.get_model_service("/drift/latest")

        if result.ok:
            return result

        return self.get_model_service("/drift")

    def send_drift_webhook(
        self,
        *,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> ApiResult:
        return self.post_agent(
            "/webhooks/drift",
            payload,
            headers={
                "Content-Type": "application/json",
                "X-Contract-Version": "v1",
                "X-Idempotency-Key": idempotency_key,
            },
        )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")