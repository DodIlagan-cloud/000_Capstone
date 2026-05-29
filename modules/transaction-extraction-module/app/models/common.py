"""M7 - Transaction Extraction Module Start
Defines shared API response models.
M7 End"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    extraction: dict[str, object]


class RootResponse(BaseModel):
    service: str
    version: str
    message: str
