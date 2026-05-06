from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.drift_webhook import DriftSeverity


class DriftEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str

    contract_version: str
    event_type: str
    source_service: str

    model_name: str
    model_version: str | None

    previous_severity: DriftSeverity
    new_severity: DriftSeverity

    overall_score: float
    sample_size: int
    min_required_samples: int

    drift_report_json: dict[str, Any]
    metadata_json: dict[str, Any] | None

    received_at: datetime
    created_at: datetime


class DriftEventListResponse(BaseModel):
    events: list[DriftEventRead]
    total: int