"""M12 - Email Ingestion Module Start
Provides common service metadata schemas for the Email Ingestion Module.
M12 End"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    provider: str
    mode: str


class RootResponse(BaseModel):
    service: str
    version: str
    message: str
