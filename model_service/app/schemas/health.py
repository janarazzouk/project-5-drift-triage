from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    version: str
    status: str
    model_loaded: bool
    timestamp: datetime