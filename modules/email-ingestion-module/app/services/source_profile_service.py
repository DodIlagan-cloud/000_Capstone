"""M12 - Email Ingestion Module Start
Stores mailbox source profiles without retaining raw secret values.
M12 End"""

from datetime import UTC, datetime
import json
import re

from app.config import settings
from app.models.ingestion import (
    AttachmentPolicy,
    EmailConnectionSettings,
    EmailProvider,
    EmailSourceProfile,
    EmailSourceProfileCreate,
    EmailSourceProfileList,
    EmailSourceProfileUpdate,
    PdfPasswordPolicy,
    PostProcessPolicy,
    SourceConnectionStatus,
)
from app.services.secret_service import normalize_secret_ref, secret_name_for_source, store_secret


_profiles: dict[str, EmailSourceProfile] = {}


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
    updated = existing.model_copy(update={"last_run_id": run_id, "last_run_status": status})
    if _use_azure_sql():
        _upsert_source_profile_sql(updated)
        return
    _profiles[source_id] = updated


def clear_source_profiles() -> None:
    _profiles.clear()


def _source_id(display_name: str, email_address: str) -> str:
    raw = f"{display_name}-{email_address.split('@')[0]}"
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return normalized or "email-source"


def _use_azure_sql() -> bool:
    return settings.email_source_config_store.lower() == "azure_sql" and bool(settings.azure_sql_connectionstring)


def _connection_string() -> str:
    connection_string = settings.azure_sql_connectionstring or ""
    if "Driver=" not in connection_string:
        connection_string = "Driver={ODBC Driver 18 for SQL Server};" + connection_string
    return (
        connection_string
        .replace("Initial Catalog=", "Database=")
        .replace("User ID=", "UID=")
        .replace("Password=", "PWD=")
        .replace("Encrypt=True", "Encrypt=yes")
        .replace("Encrypt=False", "Encrypt=no")
        .replace("TrustServerCertificate=True", "TrustServerCertificate=yes")
        .replace("TrustServerCertificate=False", "TrustServerCertificate=no")
    )


def _connect_sql():
    import pyodbc

    return pyodbc.connect(_connection_string(), timeout=10, autocommit=False)


def _list_source_profiles_sql() -> list[EmailSourceProfile]:
    with _connect_sql() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                   connection_status, sender_allowlist_json, subject_contains_json,
                   connection_settings_json, attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                   last_tested_at_utc, last_run_id, last_run_status
            FROM dbo.email_ingestion_sources
            ORDER BY display_name
            """
        )
        return [_row_to_profile(row) for row in cursor.fetchall()]


def _get_source_profile_sql(source_id: str) -> EmailSourceProfile | None:
    with _connect_sql() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                   connection_status, sender_allowlist_json, subject_contains_json,
                   connection_settings_json, attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                   last_tested_at_utc, last_run_id, last_run_status
            FROM dbo.email_ingestion_sources
            WHERE source_id = ?
            """,
            source_id,
        )
        row = cursor.fetchone()
        return _row_to_profile(row) if row else None


def _upsert_source_profile_sql(profile: EmailSourceProfile) -> None:
    with _connect_sql() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            MERGE dbo.email_ingestion_sources AS target
            USING (SELECT ? AS source_id) AS source
                ON target.source_id = source.source_id
            WHEN MATCHED THEN UPDATE SET
                display_name = ?, provider = ?, email_address = ?, enabled = ?, folder = ?, secret_ref = ?,
                connection_status = ?, sender_allowlist_json = ?, subject_contains_json = ?, connection_settings_json = ?,
                attachment_policy_json = ?, pdf_password_policy_json = ?, post_process_policy_json = ?,
                last_tested_at_utc = TRY_CONVERT(datetime2(3), ?), last_run_id = ?, last_run_status = ?,
                updated_at_utc = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (
                source_id, display_name, provider, email_address, enabled, folder, secret_ref,
                connection_status, sender_allowlist_json, subject_contains_json, connection_settings_json,
                attachment_policy_json, pdf_password_policy_json, post_process_policy_json,
                last_tested_at_utc, last_run_id, last_run_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRY_CONVERT(datetime2(3), ?), ?, ?);
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
            profile.last_tested_at,
            profile.last_run_id,
            profile.last_run_status,
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
            profile.last_tested_at,
            profile.last_run_id,
            profile.last_run_status,
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
        last_tested_at=row.last_tested_at_utc.isoformat() if row.last_tested_at_utc else None,
        last_run_id=row.last_run_id,
        last_run_status=row.last_run_status,
    )
