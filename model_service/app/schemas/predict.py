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