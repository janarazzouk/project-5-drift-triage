from typing import Any

from app.clients.model_service_client import ModelServiceClient
from app.schemas.rollback import RollbackResult


class RollbackTool:
    def __init__(
        self,
        *,
        model_service_client: ModelServiceClient,
    ):
        self.model_service_client = model_service_client

    def run(
        self,
        payload: dict[str, Any],
    ) -> RollbackResult:
        raw_result = self.model_service_client.request_rollback(payload)

        completed = bool(
            raw_result.get("rolled_back")
            or raw_result.get("success")
            or raw_result.get("completed")
        )

        return RollbackResult(
            completed=completed,
            raw_result=raw_result,
        )