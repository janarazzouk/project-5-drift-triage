from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.job import WorkerJobEnvelope


class ToolResult(BaseModel):
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class BaseJob(ABC):
    @abstractmethod
    def run(
        self,
        job: WorkerJobEnvelope,
    ) -> ToolResult:
        raise NotImplementedError