"""M12 - Email Ingestion Module Start
Provides the automated email ingestion endpoint.
M12 End"""

from fastapi import APIRouter, Depends

from app.models.ingestion import AutomatedEmailIngestionRequest, AutomatedEmailIngestionResult
from app.services.auth_service import require_email_ingestion_auth
from app.services.ingestion_service import run_automated_email_ingestion


router = APIRouter(
    prefix="/email-ingestions",
    tags=["email-ingestion"],
    dependencies=[Depends(require_email_ingestion_auth)],
)


@router.post("/automated-runs", response_model=AutomatedEmailIngestionResult)
def create_automated_email_ingestion(request: AutomatedEmailIngestionRequest) -> AutomatedEmailIngestionResult:
    return run_automated_email_ingestion(request)
