from typing import Any

from pydantic import BaseModel, Field


class RetrainResult(BaseModel):
    completed: bool
    exit_code: int | None = None

    command: str
    working_dir: str

    started_at: str
    finished_at: str
    duration_seconds: float

    stdout_tail: str = ""
    stderr_tail: str = ""

    error_message: str | None = None

    training_summary_found: bool = False
    training_summary_path: str | None = None

    artifact_dir: str | None = None
    missing_artifacts: list[str] = Field(default_factory=list)
    stale_artifacts: list[str] = Field(default_factory=list)
    produced_artifacts: list[str] = Field(default_factory=list)

    archived_previous_artifacts_dir: str | None = None

    registered_model_name: str | None = None
    model_version: str | None = None
    mlflow_run_id: str | None = None
    mlflow_model_uri: str | None = None

    selected_threshold: float | None = None
    test_metrics: dict[str, Any] = Field(default_factory=dict)

    training_summary: dict[str, Any] = Field(default_factory=dict)