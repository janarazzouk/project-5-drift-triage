from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(
        default=None,
        description="Optional ID for tracing this prediction. If missing, the API generates one.",
    )

    features: dict[str, Any] = Field(
        ...,
        description=(
            "Dictionary containing the model input columns and their values. "
            "The required columns are loaded from artifacts/schema.json."
        ),
    )

    @field_validator("features")
    @classmethod
    def features_must_not_be_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("features cannot be empty.")

        return value


class PredictionResponse(BaseModel):
    request_id: str
    probability: float
    predicted_class: int
    threshold: float
    model_version: str | None = None
    saved: bool = True


class HealthResponse(BaseModel):
    service: str
    version: str
    status: str
    model_loaded: bool
    timestamp: datetime


class RegistryResponse(BaseModel):
    model_name: str
    model_version: str | None
    threshold: float
    metrics: dict[str, Any]
    environment: dict[str, Any]
    artifact_paths: dict[str, str]


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


class ReplayFixtureResponse(BaseModel):
    fixture: dict[str, Any]


class ReplayComparisonItem(BaseModel):
    index: int
    request_id: str
    expected_probability: float | None = None
    actual_probability: float
    probability_difference: float | None = None
    expected_prediction: int | None = None
    actual_prediction: int
    prediction_matches: bool | None = None


class ReplayComparisonResponse(BaseModel):
    total_rows: int
    threshold: float
    max_probability_difference: float | None = None
    prediction_mismatches: int
    results: list[ReplayComparisonItem]