"""M5 - Document Parsing Module Start
Provides common service metadata schemas for the Document Parsing Module.
M5/M6 End"""

from pydantic import BaseModel


class OcrReadiness(BaseModel):
    enabled: bool
    engine: str
    languages: list[str]
    tesseract_cmd: str = ""
    tessdata_prefix: str = ""
    tesseract_available: bool
    renderer: str
    renderer_available: bool


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    ocr: OcrReadiness


class RootResponse(BaseModel):
    service: str
    version: str
    message: str
