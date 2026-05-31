"""M8 - Data Validation Module Start
Defines shared API response models.
M8 End"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    validation: dict[str, object]


class RootResponse(BaseModel):
    service: str
    version: str
    message: str
