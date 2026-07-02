"""M12 - Email Ingestion Module Start
Provides mailbox source profile setup endpoints.
M12 End"""

from fastapi import APIRouter, Depends, HTTPException

from app.models.ingestion import (
    EmailSourceProfile,
    EmailSourceProfileCreate,
    EmailSourceProfileList,
    EmailSourceProfileUpdate,
    SourceConnectionStatus,
    TestConnectionRequest,
    TestConnectionResult,
)
from app.services.secret_service import SecretResolutionError, resolve_secret
from app.services.auth_service import require_email_ingestion_auth
from app.services.source_profile_service import (
    SourceProfileConflictError,
    create_source_profile,
    delete_source_profile,
    get_source_profile,
    list_source_profiles,
    mark_connection_test,
    update_source_profile,
)
from app.services.imap_service import ImapProviderError, supports_imap_provider, test_connection


router = APIRouter(
    prefix="/email-ingestion-sources",
    tags=["email-ingestion-sources"],
    dependencies=[Depends(require_email_ingestion_auth)],
)


@router.get("", response_model=EmailSourceProfileList)
def list_sources() -> EmailSourceProfileList:
    return list_source_profiles()


@router.post("", response_model=EmailSourceProfile)
def create_source(request: EmailSourceProfileCreate) -> EmailSourceProfile:
    try:
        return create_source_profile(request)
    except SourceProfileConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/{source_id}", response_model=EmailSourceProfile)
def update_source(source_id: str, request: EmailSourceProfileUpdate) -> EmailSourceProfile:
    profile = update_source_profile(source_id, request)
    if profile is None:
        raise HTTPException(status_code=404, detail="Email source profile was not found.")
    return profile


@router.delete("/{source_id}")
def delete_source(source_id: str) -> dict:
    if not delete_source_profile(source_id):
        raise HTTPException(status_code=404, detail="Email source profile was not found.")
    return {"status": "deleted", "source_id": source_id}


@router.post("/{source_id}/test-connection", response_model=TestConnectionResult)
def test_source_connection(source_id: str, request: TestConnectionRequest) -> TestConnectionResult:
    profile = get_source_profile(source_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Email source profile was not found.")

    test_profile = profile.model_copy(update={"folder": request.folder}) if request.folder else profile
    # Check provider support before touching the secret store so unsupported
    # providers do not trigger pointless Key Vault / SQL reads.
    if not supports_imap_provider(profile.provider):
        mark_connection_test(source_id, SourceConnectionStatus.failed)
        return TestConnectionResult(
            source_id=source_id,
            status=SourceConnectionStatus.failed,
            provider=profile.provider,
            folder=test_profile.folder,
            message=f"{profile.provider.value} does not support connection testing.",
        )
    try:
        password = request.app_password or resolve_secret(profile.secret_ref)
    except SecretResolutionError as exc:
        mark_connection_test(source_id, SourceConnectionStatus.failed)
        return TestConnectionResult(
            source_id=source_id,
            status=SourceConnectionStatus.failed,
            provider=profile.provider,
            folder=test_profile.folder,
            message=str(exc),
        )
    try:
        test_connection(test_profile, password)
    except ImapProviderError as exc:
        mark_connection_test(source_id, SourceConnectionStatus.failed)
        return TestConnectionResult(
            source_id=source_id,
            status=SourceConnectionStatus.failed,
            provider=profile.provider,
            folder=test_profile.folder,
            message=str(exc),
        )

    mark_connection_test(source_id, SourceConnectionStatus.connected)
    return TestConnectionResult(
        source_id=source_id,
        status=SourceConnectionStatus.connected,
        provider=profile.provider,
        folder=test_profile.folder,
        message="IMAP connection succeeded.",
    )
