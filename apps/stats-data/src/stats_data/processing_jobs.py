"""M9 - Stats Data and Persistence Start
Persists long-running upload processing job state.
M9 End"""

from __future__ import annotations

from dataclasses import dataclass
import json
import uuid
from typing import Any


TERMINAL_STATUSES = {"completed", "failed"}


@dataclass(frozen=True)
class ProcessingJob:
    job_id: str
    ingestion_id: str | None
    uploaded_by_user_id: str | None
    original_filename: str
    source_type: str
    source_id: str | None
    sha256: str | None
    status: str
    stage: str
    message: str | None
    parse_id: str | None = None
    extraction_id: str | None = None
    validation_id: str | None = None
    result_payload: dict[str, Any] | None = None
    error_detail: str | None = None
    created_at_utc: str | None = None
    updated_at_utc: str | None = None
    completed_at_utc: str | None = None


@dataclass(frozen=True)
class ProcessingStep:
    step_id: str
    job_id: str
    document_id: str | None
    correlation_id: str | None
    module_name: str
    step_name: str
    status: str
    started_at_utc: str
    completed_at_utc: str | None
    duration_ms: int | None
    metadata: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at_utc: str | None = None


def create_processing_job(
    connection: Any,
    *,
    ingestion_id: str | None,
    uploaded_by_user_id: str | None,
    original_filename: str,
    source_type: str = "manual_upload",
    source_id: str | None = None,
    sha256: str | None = None,
    message: str | None = None,
) -> ProcessingJob:
    """Create a durable processing job row."""

    filename = _required_text(original_filename, "original_filename")
    job_id = str(uuid.uuid4())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
INSERT INTO dbo.document_processing_jobs (
    job_id,
    ingestion_id,
    uploaded_by_user_id,
    original_filename,
    source_type,
    source_id,
    sha256,
    status,
    stage,
    message
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
""",
            job_id,
            _text(ingestion_id),
            _text(uploaded_by_user_id),
            filename,
            _text(source_type) or "manual_upload",
            _text(source_id),
            _text(sha256),
            "queued",
            "uploaded",
            _text(message) or "Document uploaded. Waiting to read the document.",
        )
        connection.commit()
    finally:
        _close_cursor(cursor)
    return get_processing_job(connection, job_id)


def append_processing_step(
    connection: Any,
    job_id: str,
    *,
    module_name: str,
    step_name: str,
    status: str,
    started_at_utc: str,
    completed_at_utc: str | None = None,
    duration_ms: int | None = None,
    document_id: str | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> ProcessingStep:
    """Append a durable processing-step timing summary."""

    requested_job_id = _required_text(job_id, "job_id")
    step_id = str(uuid.uuid4())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
INSERT INTO dbo.document_processing_steps (
    step_id,
    job_id,
    document_id,
    correlation_id,
    module_name,
    step_name,
    status,
    started_at_utc,
    completed_at_utc,
    duration_ms,
    metadata_json,
    error_code,
    error_message
)
VALUES (?, ?, ?, ?, ?, ?, ?, CONVERT(datetime2(3), ?, 126), CONVERT(datetime2(3), ?, 126), ?, ?, ?, ?);
""",
            step_id,
            requested_job_id,
            _text(document_id),
            _text(correlation_id),
            _required_text(module_name, "module_name"),
            _required_text(step_name, "step_name"),
            _required_text(status, "status"),
            _required_text(started_at_utc, "started_at_utc"),
            _text(completed_at_utc),
            _non_negative_int(duration_ms, "duration_ms") if duration_ms is not None else None,
            _json_payload(metadata),
            _text(error_code),
            _text(error_message),
        )
        connection.commit()
    finally:
        _close_cursor(cursor)
    return get_processing_step(connection, step_id)


def list_processing_steps(connection: Any, job_id: str) -> list[ProcessingStep]:
    """Fetch timing summaries for one processing job in insert order."""

    requested_job_id = _required_text(job_id, "job_id")
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
SELECT
    step_id,
    job_id,
    document_id,
    correlation_id,
    module_name,
    step_name,
    status,
    CONVERT(varchar(33), started_at_utc, 126) AS started_at_utc,
    CONVERT(varchar(33), completed_at_utc, 126) AS completed_at_utc,
    duration_ms,
    metadata_json,
    error_code,
    error_message,
    CONVERT(varchar(33), created_at_utc, 126) AS created_at_utc
FROM dbo.document_processing_steps
WHERE job_id = ?
ORDER BY created_at_utc, step_id;
""",
            requested_job_id,
        )
        return [_processing_step(row) for row in cursor.fetchall()]
    finally:
        _close_cursor(cursor)


def get_processing_step(connection: Any, step_id: str) -> ProcessingStep:
    """Fetch a processing-step timing summary by identifier."""

    requested_step_id = _required_text(step_id, "step_id")
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
SELECT
    step_id,
    job_id,
    document_id,
    correlation_id,
    module_name,
    step_name,
    status,
    CONVERT(varchar(33), started_at_utc, 126) AS started_at_utc,
    CONVERT(varchar(33), completed_at_utc, 126) AS completed_at_utc,
    duration_ms,
    metadata_json,
    error_code,
    error_message,
    CONVERT(varchar(33), created_at_utc, 126) AS created_at_utc
FROM dbo.document_processing_steps
WHERE step_id = ?;
""",
            requested_step_id,
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("processing step was not found.")
        return _processing_step(row)
    finally:
        _close_cursor(cursor)


def update_processing_job(
    connection: Any,
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    parse_id: str | None = None,
    extraction_id: str | None = None,
    validation_id: str | None = None,
    result_payload: dict[str, Any] | None = None,
    error_detail: str | None = None,
) -> ProcessingJob:
    """Update a processing job and return the fresh row."""

    current = get_processing_job(connection, job_id)
    if current.status in TERMINAL_STATUSES:
        return current

    next_status = _text(status) or current.status
    next_stage = _text(stage) or current.stage
    completed_sql = ", completed_at_utc = CASE WHEN ? IN ('completed', 'failed') THEN SYSUTCDATETIME() ELSE completed_at_utc END"
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""
UPDATE dbo.document_processing_jobs
SET status = ?,
    stage = ?,
    message = ?,
    parse_id = COALESCE(?, parse_id),
    extraction_id = COALESCE(?, extraction_id),
    validation_id = COALESCE(?, validation_id),
    result_payload_json = ?,
    error_detail = ?,
    updated_at_utc = SYSUTCDATETIME()
    {completed_sql}
WHERE job_id = ?;
""",
            next_status,
            next_stage,
            _text(message) if message is not None else current.message,
            _text(parse_id),
            _text(extraction_id),
            _text(validation_id),
            _json_payload(result_payload) if result_payload is not None else _json_payload(current.result_payload),
            _text(error_detail) if error_detail is not None else current.error_detail,
            next_status,
            current.job_id,
        )
        connection.commit()
    finally:
        _close_cursor(cursor)
    return get_processing_job(connection, current.job_id)


def get_processing_job(connection: Any, job_id: str) -> ProcessingJob:
    """Fetch a processing job by identifier."""

    requested_job_id = _required_text(job_id, "job_id")
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
SELECT
    job_id,
    ingestion_id,
    uploaded_by_user_id,
    original_filename,
    source_type,
    source_id,
    sha256,
    status,
    stage,
    message,
    parse_id,
    extraction_id,
    validation_id,
    result_payload_json,
    error_detail,
    CONVERT(varchar(33), created_at_utc, 126) AS created_at_utc,
    CONVERT(varchar(33), updated_at_utc, 126) AS updated_at_utc,
    CONVERT(varchar(33), completed_at_utc, 126) AS completed_at_utc
FROM dbo.document_processing_jobs
WHERE job_id = ?;
""",
            requested_job_id,
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("processing job was not found.")
        return _processing_job(row)
    finally:
        _close_cursor(cursor)


def _processing_job(row: Any) -> ProcessingJob:
    payload = _json_loads(_row_value(row, "result_payload_json"))
    return ProcessingJob(
        job_id=str(_row_value(row, "job_id")),
        ingestion_id=_text(_row_value(row, "ingestion_id")),
        uploaded_by_user_id=_text(_row_value(row, "uploaded_by_user_id")),
        original_filename=str(_row_value(row, "original_filename")),
        source_type=str(_row_value(row, "source_type")),
        source_id=_text(_row_value(row, "source_id")),
        sha256=_text(_row_value(row, "sha256")),
        status=str(_row_value(row, "status")),
        stage=str(_row_value(row, "stage")),
        message=_text(_row_value(row, "message")),
        parse_id=_text(_row_value(row, "parse_id")),
        extraction_id=_text(_row_value(row, "extraction_id")),
        validation_id=_text(_row_value(row, "validation_id")),
        result_payload=payload,
        error_detail=_text(_row_value(row, "error_detail")),
        created_at_utc=_text(_row_value(row, "created_at_utc")),
        updated_at_utc=_text(_row_value(row, "updated_at_utc")),
        completed_at_utc=_text(_row_value(row, "completed_at_utc")),
    )


def _close_cursor(cursor: Any) -> None:
    try:
        cursor.close()
    except Exception:
        pass


def _processing_step(row: Any) -> ProcessingStep:
    return ProcessingStep(
        step_id=str(_row_value(row, "step_id")),
        job_id=str(_row_value(row, "job_id")),
        document_id=_text(_row_value(row, "document_id")),
        correlation_id=_text(_row_value(row, "correlation_id")),
        module_name=str(_row_value(row, "module_name")),
        step_name=str(_row_value(row, "step_name")),
        status=str(_row_value(row, "status")),
        started_at_utc=str(_row_value(row, "started_at_utc")),
        completed_at_utc=_text(_row_value(row, "completed_at_utc")),
        duration_ms=_optional_int(_row_value(row, "duration_ms")),
        metadata=_json_loads(_row_value(row, "metadata_json")),
        error_code=_text(_row_value(row, "error_code")),
        error_message=_text(_row_value(row, "error_message")),
        created_at_utc=_text(_row_value(row, "created_at_utc")),
    )


def _row_value(row: Any, name: str) -> Any:
    if hasattr(row, name):
        return getattr(row, name)
    if isinstance(row, dict):
        return row.get(name)
    return row[name]


def _json_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _json_loads(payload: Any) -> dict[str, Any] | None:
    if payload in (None, ""):
        return None
    value = json.loads(str(payload))
    return value if isinstance(value, dict) else None


def _required_text(value: Any, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _non_negative_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return parsed


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
