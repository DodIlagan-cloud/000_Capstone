"""M12 - Email Ingestion Module Start
Provides the automated email ingestion endpoint and run-history reads.
M12 End"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.ingestion import (
    AutomatedEmailIngestionRequest,
    AutomatedEmailIngestionResult,
    EmailIngestionRunDetail,
    EmailIngestionRunList,
    ProcessImportedRequest,
    ProcessImportedResult,
)
from app.services.auth_service import require_email_ingestion_auth, require_internal_service_auth
from app.services.ingestion_service import run_automated_email_ingestion
from app.services import run_history_service
from app.services.pipeline_runner import process_imported_run
from app.services.scheduler import run_due_profiles_with_lock


router = APIRouter(
    prefix="/email-ingestions",
    tags=["email-ingestion"],
    dependencies=[Depends(require_email_ingestion_auth)],
)


@router.post("/automated-runs", response_model=AutomatedEmailIngestionResult)
def create_automated_email_ingestion(request: AutomatedEmailIngestionRequest) -> AutomatedEmailIngestionResult:
    return run_automated_email_ingestion(request)


@router.get("/runs", response_model=EmailIngestionRunList)
def list_email_ingestion_runs(
    source_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> EmailIngestionRunList:
    return EmailIngestionRunList(runs=run_history_service.list_runs(source_id=source_id, limit=limit))


@router.get("/runs/{run_id}", response_model=EmailIngestionRunDetail)
def get_email_ingestion_run(run_id: str) -> EmailIngestionRunDetail:
    run = run_history_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Email ingestion run was not found.")
    return run


@router.post("/process-imported", response_model=ProcessImportedResult)
def process_imported(request: ProcessImportedRequest) -> ProcessImportedResult:
    """Push the imported files from an email import run through to the database.

    Drives parse -> extract -> validate -> process-to-database for each
    handed-off attachment, reading the stored bytes back from intake. The
    mailbox import behaviour is unchanged; this is the second, separate manual
    action.
    """
    result = process_imported_run(request.source_id, request.run_id)
    if result.status == "not_found":
        raise HTTPException(status_code=404, detail="No import run was found for this source.")
    return result


@router.post("/scheduled-runs", dependencies=[Depends(require_internal_service_auth)])
def run_scheduled_ingestions() -> dict:
    """Run every enabled profile whose polling cadence is due (import then ingest).

    Internal-key only (the Azure Container Apps Job cron tick), not reachable with a
    user/admin bearer token. Profiles with cadence 'off' are never run, so this is a
    no-op until schedules are configured.
    """
    return run_due_profiles_with_lock()
