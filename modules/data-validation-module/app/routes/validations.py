"""M8 - Data Validation Module Start
Provides the data validation endpoint.
M8 End"""

from fastapi import APIRouter

from app.models.validation import DataValidationRequest, DataValidationResult
from app.services.validation_service import validate_data


router = APIRouter(prefix="/validations", tags=["data-validation"])


@router.post("", response_model=DataValidationResult)
def create_validation(request: DataValidationRequest) -> DataValidationResult:
    return validate_data(request)
