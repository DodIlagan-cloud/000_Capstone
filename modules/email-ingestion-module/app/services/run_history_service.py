"""M12 - Email Ingestion Module Start
Persists email ingestion run history and supports cross-run deduplication.

This store keeps run headers and content-free candidate rows so the UI can show
recent runs and so repeated runs do not re-import the same mailbox attachment.
It mirrors the dual-store pattern used by source_profile_service: an in-memory
store for local/test runs and an Azure SQL store for cloud runtime.
M12 End"""

import json
import logging

from app.config import settings
from app.services import sql_store
from app.models.ingestion import (
    AttachmentStatus,
    EmailIngestionRunCandidate,
    EmailIngestionRunDetail,
    EmailIngestionRunSummaryRecord,
    EmailIngestionStatus,
    EmailIngestionSummary,
)


logger = logging.getLogger(__name__)

# In-memory store. Newest runs are appended; detail keeps embedded candidates.
_runs: dict[str, EmailIngestionRunDetail] = {}
_run_order: list[str] = []
# Tracks which handed-off attachments have already been pushed through the pipeline,
# so the manual button and the scheduler cannot push the same ingestion to M9 twice.
_processed_ingestions: dict[str, str] = {}

# Candidate statuses that represent an attachment that was actually imported into
# file intake. Only these mark a dedup key as already-imported for later runs.
_IMPORTED_STATUSES = {AttachmentStatus.handed_off.value}


def record_run(run: EmailIngestionRunDetail) -> None:
    """Persist a completed run header and its content-free candidate rows."""
    if _use_azure_sql():
        try:
            _record_run_sql(run)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            # A run-history write failure must not fail an ingestion that already
            # handed attachments to file intake. Log without secrets and continue.
            logger.warning(
                "M12 run history persistence failed. run_id=%s source_id=%s error=%s",
                run.run_id,
                run.source_id,
                str(exc),
            )
        return
    _runs[run.run_id] = run
    if run.run_id not in _run_order:
        _run_order.append(run.run_id)


def list_runs(source_id: str | None = None, limit: int = 20) -> list[EmailIngestionRunSummaryRecord]:
    """Return recent run headers (newest first), optionally filtered by source."""
    safe_limit = max(1, min(int(limit or 20), 100))
    if _use_azure_sql():
        try:
            return _list_runs_sql(source_id, safe_limit)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 run history read failed. source_id=%s error=%s", source_id, str(exc))
            return []
    summaries: list[EmailIngestionRunSummaryRecord] = []
    for run_id in reversed(_run_order):
        run = _runs.get(run_id)
        if run is None:
            continue
        if source_id and run.source_id != source_id:
            continue
        summaries.append(_as_summary(run))
        if len(summaries) >= safe_limit:
            break
    return summaries


def get_run(run_id: str) -> EmailIngestionRunDetail | None:
    """Return one run with its candidate detail."""
    if _use_azure_sql():
        try:
            return _get_run_sql(run_id)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 run history detail read failed. run_id=%s error=%s", run_id, str(exc))
            return None
    return _runs.get(run_id)


def is_attachment_already_imported(dedup_key: str | None) -> bool:
    """Return True if a prior run already imported this attachment identity."""
    if not dedup_key:
        return False
    if _use_azure_sql():
        try:
            return _is_already_imported_sql(dedup_key)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 dedup lookup failed. error=%s", str(exc))
            return False
    for run in _runs.values():
        for candidate in run.candidates:
            if candidate.dedup_key == dedup_key and candidate.status.value in _IMPORTED_STATUSES:
                return True
    return False


def mark_ingestion_processed(ingestion_id: str | None, document_id: str | None = None, run_id: str | None = None) -> None:
    """Record that an attachment's stored bytes were pushed through the pipeline."""
    if not ingestion_id:
        return
    if _use_azure_sql():
        try:
            _mark_processed_sql(ingestion_id, document_id, run_id)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 processed-marker write failed. ingestion_id=%s error=%s", ingestion_id, str(exc))
    _processed_ingestions[ingestion_id] = document_id or ""


def list_unprocessed_import_run_ids(source_id: str, limit: int = 5) -> list[str]:
    """Run ids (newest first) that still hold handed-off attachments which were
    never pushed through the pipeline.

    Used by the scheduler to retry an ingest that failed on an earlier tick: the
    files are already in intake, so without this the mailbox dedup would skip them
    on re-import and they would sit unprocessed indefinitely.
    """
    safe_limit = max(1, min(int(limit or 5), 20))
    if _use_azure_sql():
        try:
            return _list_unprocessed_import_run_ids_sql(source_id, safe_limit)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 unprocessed-run lookup failed. source_id=%s error=%s", source_id, str(exc))
            return []
    run_ids: list[str] = []
    for run_id in reversed(_run_order):
        run = _runs.get(run_id)
        if run is None or run.source_id != source_id:
            continue
        if any(
            candidate.status.value in _IMPORTED_STATUSES
            and candidate.handoff_ingestion_id
            and candidate.handoff_ingestion_id not in _processed_ingestions
            for candidate in run.candidates
        ):
            run_ids.append(run_id)
            if len(run_ids) >= safe_limit:
                break
    return run_ids


def is_ingestion_processed(ingestion_id: str | None) -> bool:
    """True if this attachment was already pushed through the pipeline (idempotency)."""
    if not ingestion_id:
        return False
    if ingestion_id in _processed_ingestions:
        return True
    if _use_azure_sql():
        try:
            return _is_processed_sql(ingestion_id)
        except Exception as exc:  # pragma: no cover - cloud persistence guard
            logger.warning("M12 processed-marker lookup failed. ingestion_id=%s error=%s", ingestion_id, str(exc))
            return False
    return False


def clear_run_history() -> None:
    _runs.clear()
    _run_order.clear()
    _processed_ingestions.clear()


def _as_summary(run: EmailIngestionRunDetail) -> EmailIngestionRunSummaryRecord:
    return EmailIngestionRunSummaryRecord(
        run_id=run.run_id,
        source_id=run.source_id,
        mode=run.mode,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        correlation_id=run.correlation_id,
        error_message=run.error_message,
        summary=run.summary,
    )


# --- Azure SQL backing store -------------------------------------------------


def _use_azure_sql() -> bool:
    return settings.email_source_config_store.lower() == "azure_sql" and bool(settings.azure_sql_connectionstring)


def _record_run_sql(run: EmailIngestionRunDetail) -> None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            MERGE {sql_store.qualified('email_ingestion_runs')} AS target
            USING (SELECT ? AS run_id) AS source
                ON target.run_id = source.run_id
            WHEN MATCHED THEN UPDATE SET
                source_id = ?, mode = ?, status = ?, started_at_utc = TRY_CONVERT(datetime2(3), ?),
                completed_at_utc = TRY_CONVERT(datetime2(3), ?), correlation_id = ?, error_message = ?,
                summary_json = ?, message_count = ?, attachment_count = ?, retrieved_count = ?,
                handed_off_count = ?, skipped_count = ?, duplicate_count = ?, failed_count = ?,
                password_required_count = ?, password_failed_count = ?
            WHEN NOT MATCHED THEN INSERT (
                run_id, source_id, mode, status, started_at_utc, completed_at_utc, correlation_id,
                error_message, summary_json, message_count, attachment_count, retrieved_count,
                handed_off_count, skipped_count, duplicate_count, failed_count, password_required_count,
                password_failed_count
            ) VALUES (?, ?, ?, ?, TRY_CONVERT(datetime2(3), ?), TRY_CONVERT(datetime2(3), ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            run.run_id,
            run.source_id, run.mode, run.status.value, run.started_at, run.completed_at,
            run.correlation_id, run.error_message, run.summary.model_dump_json(),
            run.summary.message_count, run.summary.attachment_count, run.summary.retrieved_count,
            run.summary.handed_off_count, run.summary.skipped_count, run.summary.duplicate_count,
            run.summary.failed_count, run.summary.password_required_count, run.summary.password_failed_count,
            run.run_id,
            run.source_id, run.mode, run.status.value, run.started_at, run.completed_at,
            run.correlation_id, run.error_message, run.summary.model_dump_json(),
            run.summary.message_count, run.summary.attachment_count, run.summary.retrieved_count,
            run.summary.handed_off_count, run.summary.skipped_count, run.summary.duplicate_count,
            run.summary.failed_count, run.summary.password_required_count, run.summary.password_failed_count,
        )
        cursor.execute(
            f"DELETE FROM {sql_store.qualified('email_ingestion_run_candidates')} WHERE run_id = ?", run.run_id
        )
        for candidate in run.candidates:
            cursor.execute(
                f"""
                INSERT INTO {sql_store.qualified('email_ingestion_run_candidates')} (
                    run_id, source_id, candidate_id, filename, status, sender, subject_redacted,
                    received_at, message_id, attachment_id, sha256, original_sha256, dedup_key, handoff_ingestion_id,
                    handoff_status, handoff_content_reference, handoff_error, finding_codes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                run.run_id,
                run.source_id,
                candidate.candidate_id,
                candidate.filename,
                candidate.status.value,
                candidate.sender,
                candidate.subject_redacted,
                candidate.received_at,
                candidate.message_id,
                candidate.attachment_id,
                candidate.sha256,
                candidate.original_sha256,
                candidate.dedup_key,
                candidate.handoff_ingestion_id,
                candidate.handoff_status,
                candidate.handoff_content_reference,
                candidate.handoff_error,
                json.dumps(candidate.finding_codes),
            )
        connection.commit()


def _list_runs_sql(source_id: str | None, limit: int) -> list[EmailIngestionRunSummaryRecord]:
    where = "WHERE source_id = ?" if source_id else ""
    params: list = [limit]
    if source_id:
        params.append(source_id)
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT TOP (?) run_id, source_id, mode, status, started_at_utc, completed_at_utc,
                   correlation_id, error_message, summary_json
            FROM {sql_store.qualified('email_ingestion_runs')}
            {where}
            ORDER BY started_at_utc DESC, run_id DESC
            """,
            *params,
        )
        return [_row_to_summary(row) for row in cursor.fetchall()]


def _get_run_sql(run_id: str) -> EmailIngestionRunDetail | None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT run_id, source_id, mode, status, started_at_utc, completed_at_utc,
                   correlation_id, error_message, summary_json
            FROM {sql_store.qualified('email_ingestion_runs')}
            WHERE run_id = ?
            """,
            run_id,
        )
        header = cursor.fetchone()
        if not header:
            return None
        cursor.execute(
            f"""
            SELECT candidate_id, filename, status, sender, subject_redacted, received_at,
                   message_id, attachment_id, sha256, original_sha256, dedup_key, handoff_ingestion_id,
                   handoff_status, handoff_content_reference, handoff_error, finding_codes_json
            FROM {sql_store.qualified('email_ingestion_run_candidates')}
            WHERE run_id = ?
            ORDER BY id
            """,
            run_id,
        )
        candidates = [_row_to_candidate(row) for row in cursor.fetchall()]
    summary = _row_to_summary(header)
    return EmailIngestionRunDetail(**summary.model_dump(), candidates=candidates)


def _is_already_imported_sql(dedup_key: str) -> bool:
    placeholders = ", ".join("?" for _ in _IMPORTED_STATUSES)
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT TOP (1) 1 FROM {sql_store.qualified('email_ingestion_run_candidates')}
            WHERE dedup_key = ? AND status IN ({placeholders})
            """,
            dedup_key,
            *sorted(_IMPORTED_STATUSES),
        )
        return cursor.fetchone() is not None


def _list_unprocessed_import_run_ids_sql(source_id: str, limit: int) -> list[str]:
    placeholders = ", ".join("?" for _ in _IMPORTED_STATUSES)
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT TOP (?) r.run_id
            FROM {sql_store.qualified('email_ingestion_runs')} r
            WHERE r.source_id = ?
              AND EXISTS (
                SELECT 1
                FROM {sql_store.qualified('email_ingestion_run_candidates')} c
                LEFT JOIN {sql_store.qualified('email_ingestion_processed')} p
                    ON p.ingestion_id = c.handoff_ingestion_id
                WHERE c.run_id = r.run_id
                  AND c.status IN ({placeholders})
                  AND c.handoff_ingestion_id IS NOT NULL
                  AND p.ingestion_id IS NULL
              )
            ORDER BY r.started_at_utc DESC, r.run_id DESC
            """,
            limit,
            source_id,
            *sorted(_IMPORTED_STATUSES),
        )
        return [row.run_id for row in cursor.fetchall()]


def _mark_processed_sql(ingestion_id: str, document_id: str | None, run_id: str | None) -> None:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            MERGE {sql_store.qualified('email_ingestion_processed')} AS target
            USING (SELECT ? AS ingestion_id) AS source
                ON target.ingestion_id = source.ingestion_id
            WHEN MATCHED THEN UPDATE SET document_id = ?, run_id = ?, processed_at_utc = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (ingestion_id, document_id, run_id) VALUES (?, ?, ?);
            """,
            ingestion_id, document_id, run_id, ingestion_id, document_id, run_id,
        )
        connection.commit()


def _is_processed_sql(ingestion_id: str) -> bool:
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT TOP (1) 1 FROM {sql_store.qualified('email_ingestion_processed')} WHERE ingestion_id = ?",
            ingestion_id,
        )
        return cursor.fetchone() is not None


def _row_to_summary(row) -> EmailIngestionRunSummaryRecord:
    return EmailIngestionRunSummaryRecord(
        run_id=row.run_id,
        source_id=row.source_id,
        mode=row.mode,
        status=EmailIngestionStatus(row.status),
        started_at=row.started_at_utc.isoformat() if row.started_at_utc else None,
        completed_at=row.completed_at_utc.isoformat() if row.completed_at_utc else None,
        correlation_id=row.correlation_id,
        error_message=row.error_message,
        summary=EmailIngestionSummary(**json.loads(row.summary_json or "{}")),
    )


def _row_to_candidate(row) -> EmailIngestionRunCandidate:
    return EmailIngestionRunCandidate(
        candidate_id=row.candidate_id,
        filename=row.filename,
        status=AttachmentStatus(row.status),
        sender=row.sender,
        subject_redacted=row.subject_redacted,
        received_at=row.received_at,
        message_id=row.message_id,
        attachment_id=row.attachment_id,
        sha256=row.sha256,
        original_sha256=row.original_sha256,
        dedup_key=row.dedup_key,
        handoff_ingestion_id=row.handoff_ingestion_id,
        handoff_status=row.handoff_status,
        handoff_content_reference=row.handoff_content_reference,
        handoff_error=row.handoff_error,
        finding_codes=json.loads(row.finding_codes_json or "[]"),
    )
