from typing import Any

from pydantic import BaseModel, Field


class ReplayTestResult(BaseModel):
    passed: bool
    total_rows: int
    threshold: float
    max_probability_difference: float | None = None
    prediction_mismatches: int
    raw_result: dict[str, Any] = Field(default_factory=dict)