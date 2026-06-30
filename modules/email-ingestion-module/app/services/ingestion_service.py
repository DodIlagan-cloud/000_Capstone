"""M12 - Email Ingestion Module Start
Implements the automated email attachment pathway into file intake.
M12 End"""

import base64
import hashlib
import logging
import uuid
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
    EmailIngestionStatus,
    EmailIngestionSummary,
    EmailSourceMetadata,
    FileIngestionHandoff,
    FindingSeverity,
)
from app.services.secret_service import resolve_secret
from app.services.source_profile_service import get_source_profile, mark_run
from app.services.imap_service import ImapProviderError, fetch_messages, supports_imap_provider


logger = logging.getLogger(__name__)


def run_automated_email_ingestion(request: AutomatedEmailIngestionRequest) -> AutomatedEmailIngestionResult:
    run_id = f"email_run_{uuid.uuid4().hex[:12]}"
    findings: list[EmailFinding] = []
    candidates: list[AttachmentCandidate] = []
    seen_keys: set[str] = set()
    source_profile = get_source_profile(request.source_id)
    messages = request.messages
    max_messages = _effective_max_messages(request)

    if not messages and source_profile is not None and supports_imap_provider(source_profile.provider):
        try:
            messages = fetch_messages(_profile_for_retrieval(request, source_profile), resolve_secret(source_profile.secret_ref), max_messages)
        except ImapProviderError as exc:
            finding = EmailFinding(
                code="MAILBOX_RETRIEVAL_FAILED",
                severity=FindingSeverity.error,
                message=str(exc),
            )
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
            result = AutomatedEmailIngestionResult(
                run_id=run_id,
                status=EmailIngestionStatus.failed,
                source_id=request.source_id,
                provider=source_profile.provider,
                folder=source_profile.folder,
                candidates=[],
                summary=summary,
                evaluation=EmailIngestionEvaluation(
                    run_id=run_id,
                    source_id=request.source_id,
                    provider=source_profile.provider,
                    status=EmailIngestionStatus.failed,
                    finding_counts=_finding_counts([finding]),
                    dry_run=request.policy.dry_run,
                ),
                findings=[finding],
            )
            mark_run(request.source_id, result.run_id, result.status.value)
            return result

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
            duplicate_key = f"{request.source_id}:{message.message_id}:{attachment.attachment_id}:{sha256 or attachment.filename}"
            password_rule = None
            unlocked_via_rule = False
            handoff_content_base64 = attachment.content_base64
            handoff_sha256 = sha256

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
                            attachment.content_base64, resolve_secret(candidate_rule.password_secret_ref)
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

            candidates.append(
                AttachmentCandidate(
                    candidate_id=f"email_attachment_{uuid.uuid4().hex[:12]}",
                    status=status,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size_bytes=attachment.size_bytes,
                    sha256=sha256,
                    source=source,
                    handoff=handoff,
                    password_state=password_state,
                    password_rule_id=password_rule.rule_id if password_rule else None,
                    password_secret_ref=password_rule.password_secret_ref if password_rule else None,
                    findings=candidate_findings,
                )
            )

    findings.extend(finding for candidate in candidates for finding in candidate.findings)
    summary = _summarize(messages, request, candidates)
    status = _result_status(summary)
    finding_counts = _finding_counts(findings)

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
            timeout=10.0,
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
    return content.startswith(b"%PDF") and b"/Encrypt" in content[:4096]


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
