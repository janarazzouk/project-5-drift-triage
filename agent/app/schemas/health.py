from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    version: str
    status: str
    database_connected: bool
    redis_connected: bool
    timestamp: datetime