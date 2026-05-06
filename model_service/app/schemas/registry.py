from typing import Any

from pydantic import BaseModel


class RegistryResponse(BaseModel):
    model_name: str
    model_version: str | None
    threshold: float
    metrics: dict[str, Any]
    environment: dict[str, Any]
    artifact_paths: dict[str, str]