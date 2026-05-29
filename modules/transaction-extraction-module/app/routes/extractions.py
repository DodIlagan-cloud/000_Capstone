"""M7 - Transaction Extraction Module Start
Provides the transaction extraction endpoint.
M7 End"""

from fastapi import APIRouter

from app.models.extraction import TransactionExtractionRequest, TransactionExtractionResult
from app.services.extraction_service import extract_transactions


router = APIRouter(prefix="/extractions", tags=["transaction-extraction"])


@router.post("", response_model=TransactionExtractionResult)
def create_extraction(request: TransactionExtractionRequest) -> TransactionExtractionResult:
    return extract_transactions(request)
