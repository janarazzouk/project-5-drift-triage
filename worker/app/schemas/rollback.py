from typing import Any

from pydantic import BaseModel, Field


class RollbackResult(BaseModel):
    completed: bool
    raw_result: dict[str, Any] = Field(default_factory=dict)