from typing import Any

from pydantic import BaseModel


class ReplayFixtureResponse(BaseModel):
    fixture: dict[str, Any]