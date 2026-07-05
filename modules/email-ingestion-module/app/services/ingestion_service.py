"""M12 - Email Ingestion Module Start
Implements the automated email attachment pathway into file intake.
M12 End"""

import base64
import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePath

import httpx

from app.config import settings
from app.models.ingestion import (
    AttachmentCandidate,
    AttachmentStatus,
    AutomatedEmailIngestionRequest,
    AutomatedEmailIngestionResult,
    EmailFinding,
    EmailIngestionEvaluation,
    EmailIngestionRunCandidate,
    EmailIngestionRunDetail,
    EmailIngestionStatus,
    EmailIngestionSummary,
    EmailSourceMetadata,
    FileIngestionHandoff,
    FindingSeverity,
)
from app.services import run_history_service
from app.services.schedule_rules import parse_iso
from app.services.secret_service import SecretResolutionError, resolve_secret
from app.services.source_profile_service import get_source_profile, mark_run
from app.services.imap_service import ImapProviderError, apply_post_process, fetch_messages, supports_imap_provider


logger = logging.getLogger(__name__)


def run_automated_email_ingestion(request: AutomatedEmailIngestionRequest) -> AutomatedEmailIngestionResult:
    run_id = f"email_run_{uuid.uuid4().hex[:12]}"
    correlation_id = f"email_corr_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(UTC).isoformat()
    findings: list[EmailFinding] = []
    candidates: list[AttachmentCandidate] = []
    run_candidate_records: list[EmailIngestionRunCandidate] = []
    seen_keys: set[str] = set()
    source_profile = get_source_profile(request.source_id)
    messages = request.messages
    max_messages = _effective_max_messages(request)
    mode = _run_mode(request)
    mailbox_password: str | None = None
    retrieval_profile = None
    retrieved_from_imap = False
    processed_internet_ids: set[str] = set()

    logger.info(
        "M12 email ingestion run started. run_id=%s correlation_id=%s source_id=%s mode=%s",
        run_id,
        correlation_id,
        request.source_id,
        mode,
    )

    if not messages and source_profile is not None and supports_imap_provider(source_profile.provider):
        try:
            mailbox_password = resolve_secret(source_profile.secret_ref)
        except SecretResolutionError as exc:
            return _finalize_failure(
                request, run_id, correlation_id, started_at, mode, source_profile,
                code="MAILBOX_SECRET_UNREADABLE", message=str(exc),
            )
        retrieval_profile = _profile_for_retrieval(request, source_profile)
        received_after, received_before = _retrieval_window(request)
        skipped_oversized: list[dict] = []
        try:
            messages = fetch_messages(
                retrieval_profile,
                mailbox_password,
                max_messages,
                received_after=received_after,
                received_before=received_before,
                skipped_messages=skipped_oversized,
            )
            retrieved_from_imap = True
        except ImapProviderError as exc:
            return _finalize_failure(
                request, run_id, correlation_id, started_at, mode, source_profile,
                code="MAILBOX_RETRIEVAL_FAILED", message=str(exc),
            )
        # A message dropped by the pre-fetch size guard must be visible: a small,
        # valid PDF inside a large MIME email would otherwise disappear without a
        # candidate row or finding.
        for skipped in skipped_oversized:
            findings.append(
                EmailFinding(
                    code="EMAIL_MESSAGE_FETCH_SKIPPED_TOO_LARGE",
                    severity=FindingSeverity.warning,
                    message=(
                        f"Email message was skipped before download: total message size "
                        f"{skipped.get('size_bytes')} bytes exceeds the fetch safety limit "
                        f"{skipped.get('limit_bytes')} bytes. A small PDF inside a large email "
                        "is also skipped; raise MAX_ATTACHMENT_SIZE_BYTES if this message must be imported."
                    ),
                    message_id=skipped.get("message_id"),
                )
            )

    allowed_extensions = {
        item.lower() for item in _policy_values(
            request.policy.allowed_extensions,
            source_profile.attachment_policy.allowed_extensions if source_profile else None,
            settings.allowed_attachment_extensions,
        )
    }
    allowed_mime_types = {
        item.lower() for item in _policy_values(
            request.policy.allowed_mime_types,
            source_profile.attachment_policy.allowed_mime_types if source_profile else None,
            settings.allowed_attachment_mime_types,
        )
    }
    max_size = (
        request.policy.max_attachment_size_bytes
        or (source_profile.attachment_policy.max_attachment_size_bytes if source_profile else None)
        or settings.max_attachment_size_bytes
    )
    messages = _limit_messages(_filter_messages_for_source(request, source_profile, messages), max_messages)

    for message in messages:
        if not message.attachments:
            findings.append(
                EmailFinding(
                    code="EMAIL_NO_ATTACHMENTS",
                    severity=FindingSeverity.info,
                    message="Email message contained no attachments.",
                    message_id=message.message_id,
                )
            )
            continue

        for attachment in message.attachments:
            source = EmailSourceMetadata(
                source_id=request.source_id,
                provider=request.authorization.provider or settings.email_provider,
                account_id=request.authorization.account_id,
                message_id=message.message_id,
                internet_message_id=message.internet_message_id,
                sender=message.sender,
                subject_redacted=_redact_subject(message.subject),
                received_at=message.received_at,
                attachment_id=attachment.attachment_id,
                attachment_name=attachment.filename,
            )
            candidate_findings = _validate_attachment(attachment, allowed_extensions, allowed_mime_types, max_size)
            sha256 = attachment.sha256 or _content_sha256(attachment.content_base64)
            duplicate_key = _dedup_key(request.source_id, message, attachment, sha256)
            password_rule = None
            unlocked_via_rule = False
            handoff_content_base64 = attachment.content_base64
            handoff_sha256 = sha256
            # Cross-run dedup: only attachments that were handed off and later
            # marked processed by the database-ingest step count as already
            # imported. A Blob-only handoff can still be retried if processing
            # failed before persistence.
            already_imported = (
                request.policy.deduplicate
                and duplicate_key not in seen_keys
                and run_history_service.is_attachment_already_imported(duplicate_key)
            )

            if request.policy.deduplicate and duplicate_key in seen_keys:
                candidate_findings.append(
                    EmailFinding(
                        code="DUPLICATE_EMAIL_ATTACHMENT",
                        severity=FindingSeverity.warning,
                        message="Attachment was already seen in this automated run.",
                        message_id=message.message_id,
                        attachment_name=attachment.filename,
                    )
                )
                status = AttachmentStatus.duplicate
            elif already_imported:
                candidate_findings.append(
                    EmailFinding(
                        code="DUPLICATE_EMAIL_ATTACHMENT_PREVIOUSLY_IMPORTED",
                        severity=FindingSeverity.warning,
                        message="Attachment was already imported by a previous run and was skipped.",
                        message_id=message.message_id,
                        attachment_name=attachment.filename,
                    )
                )
                status = AttachmentStatus.duplicate
            elif any(finding.severity == FindingSeverity.error for finding in candidate_findings):
                status = AttachmentStatus.skipped
            elif request.policy.detect_password_protected_pdfs and _is_password_protected_pdf(attachment):
                password_rules = _pdf_password_rules(source_profile)
                if not password_rules:
                    candidate_findings.append(
                        EmailFinding(
                            code="PDF_PASSWORD_REQUIRED",
                            severity=FindingSeverity.warning,
                            message="PDF attachment is password-protected and requires a password before parsing.",
                            message_id=message.message_id,
                            attachment_name=attachment.filename,
                        )
                    )
                    status = AttachmentStatus.password_required
                else:
                    # Try the configured PDF password secrets in order. Raw passwords
                    # are resolved only in-memory and are never returned, logged, or
                    # written to candidate/handoff fields.
                    unlocked_bytes = None
                    for candidate_rule in password_rules:
                        unlocked_bytes = _unlock_pdf(
                            attachment.content_base64, _resolve_secret_safe(candidate_rule.password_secret_ref)
                        )
                        if unlocked_bytes is not None:
                            password_rule = candidate_rule
                            break
                    if unlocked_bytes is None:
                        candidate_findings.append(
                            EmailFinding(
                                code="PDF_PASSWORD_FAILED",
                                severity=FindingSeverity.warning,
                                message="Configured PDF passwords did not unlock the attachment.",
                                message_id=message.message_id,
                                attachment_name=attachment.filename,
                            )
                        )
                        status = AttachmentStatus.password_failed
                    else:
                        candidate_findings.append(
                            EmailFinding(
                                code="PDF_PASSWORD_UNLOCKED",
                                severity=FindingSeverity.info,
                                message="PDF attachment was unlocked using a configured saved password.",
                                message_id=message.message_id,
                                attachment_name=attachment.filename,
                            )
                        )
                        status = AttachmentStatus.unlocked
                        unlocked_via_rule = True
                        handoff_content_base64 = base64.b64encode(unlocked_bytes).decode("ascii")
                        handoff_sha256 = hashlib.sha256(unlocked_bytes).hexdigest()
            else:
                status = AttachmentStatus.retrieved

            seen_keys.add(duplicate_key)
            handoff = None
            # Retrieved attachments and rule-unlocked PDFs are both eligible to hand
            # off to file intake; unlocked PDFs carry their decrypted content.
            handoff_eligible = status in {AttachmentStatus.retrieved, AttachmentStatus.unlocked}
            if handoff_eligible and request.policy.handoff_to_file_ingestion and not request.policy.dry_run:
                handoff = _handoff_to_file_ingestion(
                    request, run_id, message.message_id, attachment, handoff_sha256, handoff_content_base64
                )
                if handoff.status == "queued":
                    status = AttachmentStatus.handed_off
                else:
                    status = AttachmentStatus.failed
                    candidate_findings.append(
                        EmailFinding(
                            code="FILE_INGESTION_HANDOFF_FAILED",
                            severity=FindingSeverity.error,
                            message=handoff.error or "File ingestion handoff did not return a queued status.",
                            message_id=message.message_id,
                            attachment_name=attachment.filename,
                        )
                    )
            elif handoff_eligible:
                handoff = FileIngestionHandoff(attempted=False)

            if status in {AttachmentStatus.password_required, AttachmentStatus.password_failed}:
                password_state = status.value
            elif unlocked_via_rule:
                password_state = AttachmentStatus.unlocked.value
            else:
                password_state = None

            candidate_id = f"email_attachment_{uuid.uuid4().hex[:12]}"
            # For rule-unlocked PDFs the bytes in file intake are the DECRYPTED
            # content, so the recorded sha256 must match those bytes; the
            # encrypted-source hash is kept as original_sha256 for provenance.
            processed_sha256 = handoff_sha256
            original_sha256 = sha256 if unlocked_via_rule and sha256 != handoff_sha256 else None
            candidates.append(
                AttachmentCandidate(
                    candidate_id=candidate_id,
                    status=status,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size_bytes=attachment.size_bytes,
                    sha256=processed_sha256,
                    original_sha256=original_sha256,
                    source=source,
                    handoff=handoff,
                    password_state=password_state,
                    password_rule_id=password_rule.rule_id if password_rule else None,
                    password_secret_ref=password_rule.password_secret_ref if password_rule else None,
                    findings=candidate_findings,
                )
            )
            run_candidate_records.append(
                EmailIngestionRunCandidate(
                    candidate_id=candidate_id,
                    filename=attachment.filename,
                    status=status,
                    sender=message.sender,
                    subject_redacted=_redact_subject(message.subject),
                    received_at=message.received_at,
                    message_id=message.message_id,
                    attachment_id=attachment.attachment_id,
                    sha256=processed_sha256,
                    original_sha256=original_sha256,
                    dedup_key=duplicate_key,
                    handoff_ingestion_id=handoff.ingestion_id if handoff else None,
                    handoff_status=handoff.status if handoff else None,
                    handoff_content_reference=handoff.content_reference if handoff else None,
                    handoff_error=handoff.error if handoff else None,
                    finding_codes=[finding.code for finding in candidate_findings],
                )
            )
            if status == AttachmentStatus.handed_off and message.internet_message_id:
                processed_internet_ids.add(message.internet_message_id)

    # Post-process only real mailbox runs that actually handed files off: mark-read /
    # move so scheduled polling does not rescan. Failure here is mailbox hygiene, not
    # an ingestion failure, so it is recorded as a warning finding and does not fail
    # the run. Default post_process_policy is a no-op.
    if (
        retrieved_from_imap
        and not request.policy.dry_run
        and mailbox_password
        and processed_internet_ids
        and retrieval_profile is not None
    ):
        try:
            apply_post_process(retrieval_profile, processed_internet_ids, mailbox_password)
        except ImapProviderError as exc:
            findings.append(
                EmailFinding(
                    code="POST_PROCESS_FAILED",
                    severity=FindingSeverity.warning,
                    message=str(exc),
                )
            )

    findings.extend(finding for candidate in candidates for finding in candidate.findings)
    summary = _summarize(messages, request, candidates)
    status = _result_status(summary)
    finding_counts = _finding_counts(findings)
    error_message = _run_error_message(findings)

    result = AutomatedEmailIngestionResult(
        run_id=run_id,
        status=status,
        source_id=request.source_id,
        provider=(source_profile.provider if source_profile else request.authorization.provider or settings.email_provider),
        folder=_effective_mailbox_folder(request, source_profile),
        candidates=candidates,
        summary=summary,
        evaluation=EmailIngestionEvaluation(
            run_id=run_id,
            source_id=request.source_id,
            provider=(source_profile.provider if source_profile else request.authorization.provider or settings.email_provider),
            status=status,
            finding_counts=finding_counts,
            dry_run=request.policy.dry_run,
        ),
        findings=findings,
    )
    mark_run(request.source_id, run_id, status.value)
    _persist_run_history(
        request, run_id, correlation_id, started_at, mode, status, summary, run_candidate_records, error_message
    )
    logger.info(
        "M12 email ingestion run completed. run_id=%s correlation_id=%s source_id=%s status=%s "
        "attachments=%s handed_off=%s duplicates=%s skipped=%s failed=%s",
        run_id,
        correlation_id,
        request.source_id,
        status.value,
        summary.attachment_count,
        summary.handed_off_count,
        summary.duplicate_count,
        summary.skipped_count,
        summary.failed_count,
    )
    return result


def _run_mode(request: AutomatedEmailIngestionRequest) -> str:
    if request.mode:
        return request.mode
    return "dry_run" if request.policy.dry_run else "handoff"


def _resolve_secret_safe(secret_ref: str | None) -> str | None:
    # Used for PDF password rules: a corrupt/unreadable saved secret should make
    # the unlock attempt fail (password_failed), not raise a 500. The raw secret
    # is never logged here.
    try:
        return resolve_secret(secret_ref)
    except SecretResolutionError:
        return None


def _run_error_message(findings: list[EmailFinding]) -> str | None:
    error = next((finding for finding in findings if finding.severity == FindingSeverity.error), None)
    return error.message if error else None


def _persist_run_history(
    request: AutomatedEmailIngestionRequest,
    run_id: str,
    correlation_id: str,
    started_at: str,
    mode: str,
    status: EmailIngestionStatus,
    summary: EmailIngestionSummary,
    run_candidate_records: list[EmailIngestionRunCandidate],
    error_message: str | None,
) -> None:
    # Persisting run history must never break an ingestion that already handed
    # attachments to file intake, so failures are swallowed inside the store.
    run_history_service.record_run(
        EmailIngestionRunDetail(
            run_id=run_id,
            source_id=request.source_id,
            mode=mode,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            correlation_id=correlation_id,
            error_message=error_message,
            summary=summary,
            candidates=run_candidate_records,
        )
    )


def _finalize_failure(
    request: AutomatedEmailIngestionRequest,
    run_id: str,
    correlation_id: str,
    started_at: str,
    mode: str,
    source_profile,
    code: str,
    message: str,
) -> AutomatedEmailIngestionResult:
    finding = EmailFinding(code=code, severity=FindingSeverity.error, message=message)
    summary = EmailIngestionSummary(
        message_count=0,
        attachment_count=0,
        retrieved_count=0,
        skipped_count=0,
        duplicate_count=0,
        failed_count=1,
        handed_off_count=0,
        password_required_count=0,
    )
    provider = source_profile.provider if source_profile else request.authorization.provider or settings.email_provider
    folder = source_profile.folder if source_profile else settings.default_mailbox_folder
    result = AutomatedEmailIngestionResult(
        run_id=run_id,
        status=EmailIngestionStatus.failed,
        source_id=request.source_id,
        provider=provider,
        folder=folder,
        candidates=[],
        summary=summary,
        evaluation=EmailIngestionEvaluation(
            run_id=run_id,
            source_id=request.source_id,
            provider=provider,
            status=EmailIngestionStatus.failed,
            finding_counts=_finding_counts([finding]),
            dry_run=request.policy.dry_run,
        ),
        findings=[finding],
    )
    mark_run(request.source_id, run_id, result.status.value)
    _persist_run_history(
        request, run_id, correlation_id, started_at, mode, result.status, summary, [], message
    )
    logger.warning(
        "M12 email ingestion run failed. run_id=%s correlation_id=%s source_id=%s code=%s",
        run_id,
        correlation_id,
        request.source_id,
        code,
    )
    return result


def _policy_values(request_values: list[str] | None, profile_values: list[str] | None, defaults: list[str]) -> list[str]:
    if request_values:
        return request_values
    if profile_values:
        return profile_values
    return defaults


def _effective_max_messages(request: AutomatedEmailIngestionRequest) -> int:
    if request.retrieval.max_messages is None:
        return settings.default_max_messages
    return request.retrieval.max_messages


def _retrieval_window(request: AutomatedEmailIngestionRequest) -> tuple[datetime | None, datetime | None]:
    # The request's received_after/received_before bound the IMAP search. When no
    # explicit lower bound is given, DEFAULT_LOOKBACK_HOURS applies so runs do not
    # scan the whole mailbox; 0 disables the default window.
    received_after = parse_iso(request.retrieval.received_after)
    received_before = parse_iso(request.retrieval.received_before)
    if received_after is None and settings.default_lookback_hours > 0:
        received_after = datetime.now(UTC) - timedelta(hours=settings.default_lookback_hours)
    return received_after, received_before


def _dedup_key(source_id: str, message, attachment, sha256: str | None) -> str:
    # IMAP UIDs/sequence ids are mailbox-session artifacts, so cross-run dedup keys
    # prefer the stable Message-ID header plus the content hash. The attachment
    # index + filename fallback only applies when neither stable part is available.
    message_key = message.internet_message_id or message.message_id
    content_key = sha256 or f"{attachment.attachment_id}:{attachment.filename}"
    return f"{source_id}:{message_key}:{content_key}"


def _effective_mailbox_folder(request: AutomatedEmailIngestionRequest, source_profile) -> str:
    requested = (request.retrieval.mailbox_folder or "").strip()
    if requested:
        return requested
    if source_profile:
        return source_profile.folder
    return settings.default_mailbox_folder


def _profile_for_retrieval(request: AutomatedEmailIngestionRequest, source_profile):
    return source_profile.model_copy(update={"folder": _effective_mailbox_folder(request, source_profile)})


def _limit_messages(messages, max_messages: int):
    if max_messages <= 0:
        return messages
    return messages[:max_messages]


def _validate_attachment(attachment, allowed_extensions: set[str], allowed_mime_types: set[str], max_size: int) -> list[EmailFinding]:
    findings: list[EmailFinding] = []
    extension = PurePath(attachment.filename).suffix.lower()
    content_type = attachment.content_type.lower()
    if extension not in allowed_extensions:
        findings.append(
            EmailFinding(
                code="UNSUPPORTED_ATTACHMENT_EXTENSION",
                severity=FindingSeverity.error,
                message="Attachment extension is not allowed for email ingestion.",
                attachment_name=attachment.filename,
            )
        )
    if content_type not in allowed_mime_types and not _is_generic_pdf_mime(extension, content_type):
        findings.append(
            EmailFinding(
                code="UNSUPPORTED_ATTACHMENT_MIME_TYPE",
                severity=FindingSeverity.error,
                message="Attachment content type is not allowed for email ingestion.",
                attachment_name=attachment.filename,
            )
        )
    if attachment.size_bytes <= 0:
        findings.append(
            EmailFinding(
                code="EMPTY_EMAIL_ATTACHMENT",
                severity=FindingSeverity.error,
                message="Attachment size must be greater than zero.",
                attachment_name=attachment.filename,
            )
        )
    if max_size > 0 and attachment.size_bytes > max_size:
        findings.append(
            EmailFinding(
                code="EMAIL_ATTACHMENT_TOO_LARGE",
                severity=FindingSeverity.error,
                message="Attachment exceeds the configured email ingestion size limit.",
                attachment_name=attachment.filename,
            )
        )
    return findings


def _is_generic_pdf_mime(extension: str, content_type: str) -> bool:
    return extension == ".pdf" and content_type in {
        "application/octet-stream",
        "binary/octet-stream",
        "application/x-download",
        "application/download",
    }


def _handoff_to_file_ingestion(
    request,
    run_id: str,
    message_id: str,
    attachment,
    sha256: str | None,
    content_base64: str | None = None,
) -> FileIngestionHandoff:
    payload_base64 = content_base64 if content_base64 is not None else attachment.content_base64
    trace_source_id = f"{request.source_id}:{message_id}:{attachment.attachment_id}"
    if not payload_base64:
        logger.warning(
            "M12 email attachment handoff skipped. run_id=%s source_id=%s message_id=%s attachment_id=%s reason=%s",
            run_id,
            request.source_id,
            message_id,
            attachment.attachment_id,
            "missing_attachment_content",
        )
        return FileIngestionHandoff(attempted=True, error="Attachment content is required for file ingestion handoff.")

    try:
        content = base64.b64decode(payload_base64, validate=True)
        logger.info(
            "M12 email attachment handoff started. run_id=%s source_id=%s message_id=%s attachment_id=%s "
            "handoff_source_id=%s filename=%s sha256=%s size_bytes=%s",
            run_id,
            request.source_id,
            message_id,
            attachment.attachment_id,
            trace_source_id,
            attachment.filename,
            sha256,
            len(content),
        )
        response = httpx.post(
            f"{settings.file_ingestion_base_url}/api/v1/ingestions",
            headers=_handoff_headers(),
            data={
                "validation_status": "accepted",
                "validation_sha256": sha256 or "",
                "detected_mime_type": attachment.content_type,
                "source_type": "email_attachment",
                "source_id": trace_source_id,
                "idempotency_key": trace_source_id,
            },
            files={"file": (attachment.filename, content, attachment.content_type)},
            timeout=float(settings.handoff_timeout_seconds),
        )
        payload = response.json()
        content_reference = (payload.get("handoff") or {}).get("content_reference")
        log_method = logger.info if response.is_success and payload.get("status") == "queued" else logger.warning
        log_method(
            "M12 email attachment handoff completed. run_id=%s source_id=%s message_id=%s attachment_id=%s "
            "handoff_source_id=%s ingestion_id=%s handoff_status=%s content_reference=%s http_status=%s",
            run_id,
            request.source_id,
            message_id,
            attachment.attachment_id,
            trace_source_id,
            payload.get("ingestion_id"),
            payload.get("status"),
            content_reference,
            response.status_code,
        )
        return FileIngestionHandoff(
            attempted=True,
            ingestion_id=payload.get("ingestion_id"),
            status=payload.get("status"),
            content_reference=content_reference,
            error=None if response.is_success else f"File ingestion returned HTTP {response.status_code}.",
        )
    except Exception as exc:
        logger.warning(
            "M12 email attachment handoff failed. run_id=%s source_id=%s message_id=%s attachment_id=%s "
            "handoff_source_id=%s error=%s",
            run_id,
            request.source_id,
            message_id,
            attachment.attachment_id,
            trace_source_id,
            str(exc),
        )
        return FileIngestionHandoff(attempted=True, error=str(exc))


def _handoff_headers() -> dict[str, str]:
    if not settings.stats_internal_api_key:
        return {}
    return {"X-Stats-Internal-Key": settings.stats_internal_api_key}


def _content_sha256(content_base64: str | None) -> str | None:
    if not content_base64:
        return None
    try:
        content = base64.b64decode(content_base64, validate=True)
    except Exception:
        return None
    return hashlib.sha256(content).hexdigest()


def _is_password_protected_pdf(attachment) -> bool:
    if attachment.is_password_protected is not None:
        return attachment.is_password_protected
    if PurePath(attachment.filename).suffix.lower() != ".pdf" or not attachment.content_base64:
        return False
    try:
        content = base64.b64decode(attachment.content_base64, validate=True)
    except Exception:
        return False
    if not content.startswith(b"%PDF"):
        return False
    try:
        import fitz  # PyMuPDF, packaged in the Stats runtime image.

        document = fitz.open(stream=content, filetype="pdf")
        try:
            return bool(document.needs_pass)
        finally:
            document.close()
    except Exception:
        # Some real statements are malformed enough that the PDF engine cannot
        # open them for inspection. Fall back to scanning the decoded bytes, not
        # just the header, because encryption metadata is not guaranteed to sit
        # in the first few KB.
        return b"/Encrypt" in content


def _unlock_pdf(content_base64: str | None, password: str | None) -> bytes | None:
    # Return decrypted PDF bytes using a resolved password, or None if it cannot be
    # unlocked. The password authenticates the document in-memory only; it is never
    # returned, logged, or persisted. Any failure (missing or wrong password,
    # unreadable content, or an unavailable PDF engine) yields None so the caller
    # marks the candidate password_failed rather than exposing the secret.
    if not content_base64 or not password:
        return None
    try:
        content = base64.b64decode(content_base64, validate=True)
    except Exception:
        return None
    try:
        import fitz  # PyMuPDF, packaged in the Stats runtime image.
    except ImportError:
        return None

    document = None
    try:
        document = fitz.open(stream=content, filetype="pdf")
        if document.needs_pass and not document.authenticate(password):
            return None
        return document.tobytes()  # re-serialized without encryption
    except Exception:
        return None
    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                pass


def _pdf_password_rules(source_profile):
    if source_profile is None:
        return []
    # Mailbox-level sender/subject filters decide what attachments enter this
    # source. For locked PDFs, keep password handling simple: try all enabled
    # saved PDF password secrets in their configured order.
    return [
        rule for rule in source_profile.pdf_password_policy.password_rules
        if rule.enabled
    ]


def _filter_messages_for_source(request: AutomatedEmailIngestionRequest, source_profile, messages):
    sender_allowlist = _policy_values(
        request.retrieval.sender_allowlist,
        source_profile.sender_allowlist if source_profile else None,
        [],
    )
    subject_contains = _policy_values(
        request.retrieval.subject_contains,
        source_profile.subject_contains if source_profile else None,
        [],
    )
    return [
        message for message in messages
        if _message_passes_filters(sender_allowlist, subject_contains, message.sender, message.subject)
    ]


def _message_passes_filters(sender_allowlist: list[str], subject_contains: list[str], sender: str, subject: str | None) -> bool:
    # Sender allowlist and subject keywords are OR-ed: keep a message if it matches
    # ANY configured filter. With no filters configured, everything passes.
    checks = []
    if sender_allowlist:
        checks.append(_values_match(sender_allowlist, sender))
    if subject_contains:
        checks.append(_values_match(subject_contains, subject))
    if not checks:
        return True
    return any(checks)


def _values_match(values: list[str], candidate: str | None) -> bool:
    if not values:
        return True
    candidate_text = (candidate or "").lower()
    return any(value.lower() in candidate_text for value in values if value)


def _redact_subject(subject: str | None) -> str | None:
    if subject is None:
        return None
    if not settings.redact_email_subjects:
        return subject
    return "[redacted]"


def _summarize(messages, request: AutomatedEmailIngestionRequest, candidates: list[AttachmentCandidate]) -> EmailIngestionSummary:
    return EmailIngestionSummary(
        message_count=len(messages),
        attachment_count=len(candidates),
        retrieved_count=sum(1 for item in candidates if item.status == AttachmentStatus.retrieved),
        skipped_count=sum(1 for item in candidates if item.status == AttachmentStatus.skipped),
        duplicate_count=sum(1 for item in candidates if item.status == AttachmentStatus.duplicate),
        failed_count=sum(1 for item in candidates if item.status == AttachmentStatus.failed),
        handed_off_count=sum(1 for item in candidates if item.status == AttachmentStatus.handed_off),
        password_required_count=sum(1 for item in candidates if item.status == AttachmentStatus.password_required),
        password_failed_count=sum(1 for item in candidates if item.status == AttachmentStatus.password_failed),
    )


def _result_status(summary: EmailIngestionSummary) -> EmailIngestionStatus:
    if summary.failed_count > 0:
        return EmailIngestionStatus.failed
    if summary.attachment_count > 0 and summary.password_required_count == summary.attachment_count:
        return EmailIngestionStatus.blocked
    if summary.skipped_count > 0 or summary.duplicate_count > 0:
        return EmailIngestionStatus.completed_with_warnings
    if summary.password_required_count > 0 or summary.password_failed_count > 0:
        return EmailIngestionStatus.completed_with_warnings
    return EmailIngestionStatus.completed


def _finding_counts(findings: list[EmailFinding]) -> dict[str, int]:
    # Tallies finding severities for run evaluation metadata.
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity.value] = counts.get(finding.severity.value, 0) + 1
    return counts
