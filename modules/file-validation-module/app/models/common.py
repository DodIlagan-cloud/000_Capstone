"""M3 - File Validation Module Start
Provides common service metadata schemas for the File Validation Module.
M3 End"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class RootResponse(BaseModel):
    service: str
    version: str
    message: str
