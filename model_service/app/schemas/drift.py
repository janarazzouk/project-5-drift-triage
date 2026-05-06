from typing import Any

from pydantic import BaseModel, Field


class DriftFeatureResult(BaseModel):
    feature: str
    kind: str
    score: float
    severity: str
    details: dict[str, Any] = Field(default_factory=dict)


class DriftResponse(BaseModel):
    sample_size: int
    min_required_samples: int
    severity: str
    overall_score: float
    features: list[DriftFeatureResult]
    output_drift: dict[str, Any] | None = None