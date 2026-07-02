"""M12 - Email Ingestion Module Start
Stores mailbox source profiles without retaining raw secret values.
M12 End"""

from datetime import UTC, datetime
import json
import logging
import re

from app.config import settings
from app.services import sql_store
from app.models.ingestion import (
    AttachmentPolicy,
    EmailConnectionSettings,
    EmailProvider,
    EmailSourceProfile,
    EmailSourceProfileCreate,
    EmailSourceProfileList,
    EmailSourceProfileUpdate,
    PdfPasswordPolicy,
    PollingSchedule,
    PostProcessPolicy,
    SourceConnectionStatus,
)
from app.services.secret_service import delete_secret, normalize_secret_ref, secret_name_for_source, store_secret


logger = logging.getLogger(__name__)

_profiles: dict[str, EmailSourceProfile] = {}


class SourceProfileConflictError(RuntimeError):
    """Raised when creating a source whose source_id already exists."""


def list_source_profiles() -> EmailSourceProfileList:
    if _use_azure_sql():
        return EmailSourceProfileList(sources=_list_source_profiles_sql())
    return EmailSourceProfileList(sources=sorted(_profiles.values(), key=lambda source: source.display_name.lower()))


def get_source_profile(source_id: str) -> EmailSourceProfile | None:
    if _use_azure_sql():
        return _get_source_profile_sql(source_id)
    return _profiles.get(source_id)


def create_source_profile(request: EmailSourceProfileCreate) -> EmailSourceProfile:
    source_id = request.source_id or _source_id(request.display_name, request.email_address)
    if get_source_profile(source_id) is not None:
        # Creating must not silently overwrite an existing profile (or re-point its
        # secret_ref); updates go through PATCH.
        raise SourceProfileConflictError(
            f"An email source with id '{source_id}' already exists. Update it instead, or use a different display name."
        )
    secret_ref = request.secret_ref or (secret_name_for_source(source_id, request.provider.value) if request.app_password else None)
    secret_ref = normalize_secret_ref(secret_ref) if secret_ref else None
    store_secret(secret_ref, request.app_password)
    _store_pdf_password_rule_secrets(request.pdf_password_policy)
    profile = EmailSourceProfile(
        source_id=source_id,
        display_name=request.display_name,
        provider=request.provider,
        email_address=request.email_address,
        enabled=request.enabled,
        folder=request.folder,
        connection_settings=request.connection_settings,
        sender_allowlist=request.sender_allowlist,
        subject_contains=request.subject_contains,
        attachment_policy=request.attachment_policy,
        pdf_password_policy=request.pdf_password_policy,
        post_process_policy=request.post_process_policy,
        polling_schedule=request.polling_schedule,
        secret_ref=secret_ref,
        connection_status=SourceConnectionStatus.needs_setup if not secret_ref else SourceConnectionStatus.not_tested,
    )
    if _use_azure_sql():
        _upsert_source_profile_sql(profile)
        return profile
    _profiles[source_id] = profile
    return profile


def update_source_profile(source_id: str, request: EmailSourceProfileUpdate) -> EmailSourceProfile | None:
    existing = get_source_profile(source_id)
    if existing is None:
        return None

    if request.pdf_password_policy:
        _store_pdf_password_rule_secrets(request.pdf_password_policy)
    update_data = request.model_dump(exclude_unset=True, exclude={"app_password"})
    if request.app_password and "secret_ref" not in update_data:
        provider = update_data.get("provider") or existing.provider
        provider_value = provider.value if isinstance(provider, EmailProvider) else str(provider)
        update_data["secret_ref"] = secret_name_for_source(source_id, provider_value)
        update_data["connection_status"] = SourceConnectionStatus.not_tested
    if "secret_ref" in update_data and update_data["secret_ref"]:
        update_data["secret_ref"] = normalize_secret_ref(update_data["secret_ref"])

    # Merge then re-validate so nested policy/connection models (and their
    # password_rules) are rebuilt as typed models rather than raw dicts. This
    # keeps the in-memory and Azure SQL stores consistent, since the SQL upsert
    # serializes nested models with model_dump_json().
    merged = existing.model_dump()
    merged.update(update_data)
    updated = EmailSourceProfile.model_validate(merged)
    store_secret(updated.secret_ref, request.app_password)
    if _use_azure_sql():
        _upsert_source_profile_sql(updated)
        return updated
    _profiles[source_id] = updated
    return updated


def _store_pdf_password_rule_secrets(policy: PdfPasswordPolicy | None) -> None:
    if policy is None:
        return
    for rule in policy.password_rules:
        store_secret(rule.password_secret_ref, rule.password)


def mark_connection_test(source_id: str, status: SourceConnectionStatus) -> EmailSourceProfile | None:
    existing = get_source_profile(source_id)
    if existing is None:
        return None
    updated = existing.model_copy(
        update={
            "connection_status": status,
            "last_tested_at": datetime.now(UTC).isoformat(),
        }
    )
    if _use_azure_sql():
        _upsert_source_profile_sql(updated)
        return updated
    _profiles[source_id] = updated
    return updated


def mark_run(source_id: str, run_id: str, status: str) -> None:
    existing = get_source_profile(source_id)
    if existing is None:
        return
    updated = existing.model_copy(
        update={
            "last_run_id": run_id,
            "last_run_status": status,
            "last_run_at": datetime.now(UTC).isoformat(),
        }
    )
    if _use_azure_sql():
        _upsert_source_profile_sql(updated)
        return
    _profiles[source_id] = updated


def mark_auto_run(source_id: str, timestamp_iso: str) -> None:
    existing = get_source_profile(source_id)
    if existing is None:
        return
    updated = existing.model_copy(update={"last_auto_run_at": timestamp_iso})
    if _use_azure_sql():
        _upsert_source_profile_sql(updated)
        return
    _profiles[source_id] = updated


def delete_source_profile(source_id: str) -> bool:
    """Remove a source profile. Returns False when it does not exist.

    The profile's mailbox secret is deleted best-effort from the secret provider
    ONLY when no remaining profile references the same secret_ref (the Secret
    reference field is editable, so profiles can legitimately share one). A shared
    or undeletable secret stays in the provider to be rotated or purged manually.
    PDF password rule secrets are always left in place for the same reason.
    """
    existing = get_source_profile(source_id)
    if existing is None:
        return False
    if _use_azure_sql():
        _delete_source_profile_sql(source_id)
    else:
        _profiles.pop(source_id, None)
    _delete_secret_if_unreferenced(existing.secret_ref)
    return True


def _delete_secret_if_unreferenced(secret_ref: str | None) -> None:
    if not secret_ref:
        return
    try:
        remaining = list_source_profiles().sources
    except Exception as exc:  # pragma: no cover - store read guard
        # If the reference check cannot run, keep the secret (safe default).
        logger.warning("M12 secret reference check failed; keeping secret. error=%s", str(exc))
        return
    if any(profile.secret_ref == secret_ref for profile in remaining):
        logger.info("M12 mailbox secret kept: still referenced by another source profile.")
        return
    delete_secret(secret_ref)


def _delete_source_profile_sql(source_id: str) -> None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM {sql_store.qualified('email_ingestion_sources')} WHERE source_id = ?", source_id)
        connection.commit()


def clear_source_profiles() -> None:
    _profiles.clear()


def _source_id(display_name: str, email_address: str) -> str:
    raw = f"{display_name}-{email_address.split('@')[0]}"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return normalized or "email-source"


def _use_azure_sql() -> bool:
    return settings.email_source_config_store.lower() == "azure_sql" and bool(settings.azure_sql_connectionstring)


def _list_source_profiles_sql() -> list[EmailSourceProfile]:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                   connection_status, sender_allowlist_json, subject_contains_json,
                   connection_settings_json, attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                   polling_schedule_json, last_tested_at_utc, last_run_id, last_run_status, last_run_at_utc, last_auto_run_at_utc
            FROM {sql_store.qualified('email_ingestion_sources')}
            ORDER BY display_name
            """
        )
        profiles: list[EmailSourceProfile] = []
        for row in cursor.fetchall():
            # One bad row (e.g. an unknown provider value) must not 500 the whole
            # source list; skip it with a warning so the rest stay manageable.
            try:
                profiles.append(_row_to_profile(row))
            except Exception as exc:  # pragma: no cover - defensive row guard
                logger.warning(
                    "M12 source profile row skipped. source_id=%s error=%s",
                    getattr(row, "source_id", None),
                    str(exc),
                )
        return profiles


def _get_source_profile_sql(source_id: str) -> EmailSourceProfile | None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                   connection_status, sender_allowlist_json, subject_contains_json,
                   connection_settings_json, attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                   polling_schedule_json, last_tested_at_utc, last_run_id, last_run_status, last_run_at_utc, last_auto_run_at_utc
            FROM {sql_store.qualified('email_ingestion_sources')}
            WHERE source_id = ?
            """,
            source_id,
        )
        row = cursor.fetchone()
        return _row_to_profile(row) if row else None


def _upsert_source_profile_sql(profile: EmailSourceProfile) -> None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            MERGE {sql_store.qualified('email_ingestion_sources')} AS target
            USING (SELECT ? AS source_id) AS source
                ON target.source_id = source.source_id
            WHEN MATCHED THEN UPDATE SET
                display_name = ?, provider = ?, email_address = ?, enabled = ?, folder = ?, secret_ref = ?,
                connection_status = ?, sender_allowlist_json = ?, subject_contains_json = ?, connection_settings_json = ?,
                attachment_policy_json = ?, pdf_password_policy_json = ?, post_process_policy_json = ?,
                polling_schedule_json = ?,
                last_tested_at_utc = TRY_CONVERT(datetime2(3), ?), last_run_id = ?, last_run_status = ?,
                last_run_at_utc = TRY_CONVERT(datetime2(3), ?),
                last_auto_run_at_utc = TRY_CONVERT(datetime2(3), ?),
                updated_at_utc = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (
                source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                connection_status, sender_allowlist_json, subject_contains_json, connection_settings_json,
                attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                polling_schedule_json,
                last_tested_at_utc, last_run_id, last_run_status, last_run_at_utc, last_auto_run_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRY_CONVERT(datetime2(3), ?), ?, ?, TRY_CONVERT(datetime2(3), ?), TRY_CONVERT(datetime2(3), ?));
            """,
            profile.source_id,
            profile.display_name,
            profile.provider.value,
            profile.email_address,
            1 if profile.enabled else 0,
            profile.folder,
            profile.secret_ref,
            profile.connection_status.value,
            json.dumps(profile.sender_allowlist),
            json.dumps(profile.subject_contains),
            profile.connection_settings.model_dump_json(),
            profile.attachment_policy.model_dump_json(),
            profile.pdf_password_policy.model_dump_json(),
            profile.post_process_policy.model_dump_json(),
            profile.polling_schedule.model_dump_json(),
            profile.last_tested_at,
            profile.last_run_id,
            profile.last_run_status,
            profile.last_run_at,
            profile.last_auto_run_at,
            profile.source_id,
            profile.display_name,
            profile.provider.value,
            profile.email_address,
            1 if profile.enabled else 0,
            profile.folder,
            profile.secret_ref,
            profile.connection_status.value,
            json.dumps(profile.sender_allowlist),
            json.dumps(profile.subject_contains),
            profile.connection_settings.model_dump_json(),
            profile.attachment_policy.model_dump_json(),
            profile.pdf_password_policy.model_dump_json(),
            profile.post_process_policy.model_dump_json(),
            profile.polling_schedule.model_dump_json(),
            profile.last_tested_at,
            profile.last_run_id,
            profile.last_run_status,
            profile.last_run_at,
            profile.last_auto_run_at,
        )
        connection.commit()


def _row_to_profile(row) -> EmailSourceProfile:
    return EmailSourceProfile(
        source_id=row.source_id,
        display_name=row.display_name,
        provider=EmailProvider(row.provider),
        email_address=row.email_address,
        enabled=bool(row.enabled),
        folder=row.folder,
        connection_settings=EmailConnectionSettings(**json.loads(row.connection_settings_json or "{}")),
        secret_ref=row.secret_ref,
        connection_status=SourceConnectionStatus(row.connection_status),
        sender_allowlist=json.loads(row.sender_allowlist_json or "[]"),
        subject_contains=json.loads(row.subject_contains_json or "[]"),
        attachment_policy=AttachmentPolicy(**json.loads(row.attachment_policy_json or "{}")),
        pdf_password_policy=PdfPasswordPolicy(**json.loads(row.pdf_password_policy_json or "{}")),
        post_process_policy=PostProcessPolicy(**json.loads(row.post_process_policy_json or "{}")),
        polling_schedule=PollingSchedule(**json.loads(row.polling_schedule_json or "{}")),
        last_tested_at=row.last_tested_at_utc.isoformat() if row.last_tested_at_utc else None,
        last_run_id=row.last_run_id,
        last_run_status=row.last_run_status,
        last_run_at=row.last_run_at_utc.isoformat() if row.last_run_at_utc else None,
        last_auto_run_at=row.last_auto_run_at_utc.isoformat() if row.last_auto_run_at_utc else None,
    )
