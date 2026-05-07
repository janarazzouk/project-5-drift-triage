from typing import Any


class ResultService:
    def normalize_result(
        self,
        result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return result or {}