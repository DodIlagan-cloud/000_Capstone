"""M12 - Email Ingestion Module Start
Provides generic IMAP provider adapters behind the M12 contract.
M12 End"""

from contextlib import contextmanager
from datetime import UTC, datetime
from email import message_from_bytes
from email.message import Message
import base64
import imaplib
import ipaddress
import re
import socket
from pathlib import PurePath
from typing import Iterable

from app.models.ingestion import EmailAttachmentInput, EmailMessageInput, EmailProvider, EmailSourceProfile
from app.config import settings


class ImapProviderError(RuntimeError):
    """Raised when an IMAP mailbox cannot be accessed in a controlled way."""


@contextmanager
def _imap_errors(action: str):
    # imaplib raises IMAP4.error for protocol/login failures and OSError subclasses
    # (socket timeouts, refused connections, TLS errors) for transport failures.
    # Callers only handle ImapProviderError, so wrap everything else here to keep
    # a wrong app password or an unreachable host from surfacing as an HTTP 500.
    try:
        yield
    except ImapProviderError:
        raise
    except imaplib.IMAP4.error as exc:
        raise ImapProviderError(f"IMAP {action} failed: {_safe_exception_text(exc)}") from exc
    except OSError as exc:
        raise ImapProviderError(
            f"IMAP {action} failed: the mail server could not be reached ({_safe_exception_text(exc)})."
        ) from exc


def _safe_exception_text(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:200]


PROVIDER_HOSTS = {
    EmailProvider.yahoo_imap: "imap.mail.yahoo.com",
    EmailProvider.gmail_imap: "imap.gmail.com",
    EmailProvider.outlook_imap: "outlook.office365.com",
}


def supports_imap_provider(provider: EmailProvider | str) -> bool:
    provider_value = provider.value if isinstance(provider, EmailProvider) else str(provider)
    return provider_value in {
        EmailProvider.yahoo_imap.value,
        EmailProvider.gmail_imap.value,
        EmailProvider.outlook_imap.value,
        EmailProvider.custom_imap.value,
    }


def test_connection(profile: EmailSourceProfile, password: str | None) -> None:
    if not password:
        raise ImapProviderError("Mailbox app password secret is not available.")

    with _imap_errors("connection test"), _connect(profile) as mailbox:
        mailbox.login(profile.email_address, password)
        status, _ = mailbox.select(profile.folder, readonly=True)
        if status != "OK":
            raise _folder_open_error(profile)


def fetch_messages(
    profile: EmailSourceProfile,
    password: str | None,
    max_messages: int | None,
    received_after: datetime | None = None,
    received_before: datetime | None = None,
    skipped_messages: list[dict] | None = None,
) -> list[EmailMessageInput]:
    if not password:
        raise ImapProviderError("Mailbox app password secret is not available.")

    with _imap_errors("message retrieval"), _connect(profile) as mailbox:
        mailbox.login(profile.email_address, password)
        status, _ = mailbox.select(profile.folder, readonly=True)
        if status != "OK":
            raise _folder_open_error(profile)

        status, search_data = _search_mailbox(mailbox, profile, received_after, received_before)
        if status != "OK":
            raise ImapProviderError("IMAP message search failed.")

        # UIDs (not sequence numbers) so message identities are stable across
        # sessions; cross-run dedup and re-fetches depend on this.
        message_ids = search_data[0].split()
        if max_messages and max_messages > 0:
            message_ids = message_ids[-max_messages:]
        fetch_limit = _fetch_size_limit()
        messages: list[EmailMessageInput] = []
        for message_id in message_ids:
            if fetch_limit > 0:
                message_size = _rfc822_message_size(mailbox, message_id)
                if message_size is not None and message_size > fetch_limit:
                    # Reported back to the caller so the skip shows up as a run
                    # finding instead of the message silently disappearing.
                    if skipped_messages is not None:
                        skipped_messages.append(
                            {
                                "message_id": message_id.decode("ascii", errors="ignore"),
                                "size_bytes": message_size,
                                "limit_bytes": fetch_limit,
                            }
                        )
                    continue
            status, fetch_data = mailbox.uid("fetch", message_id, "(RFC822)")
            if status != "OK" or not fetch_data:
                continue
            raw_message = next((item[1] for item in fetch_data if isinstance(item, tuple)), None)
            if not raw_message:
                continue
            parsed = message_from_bytes(raw_message)
            message = _to_message_input(profile, message_id.decode("ascii", errors="ignore"), parsed)
            if message.attachments:
                messages.append(message)
        return messages


def apply_post_process(profile: EmailSourceProfile, internet_message_ids, password: str | None) -> None:
    """Mark-as-read and/or move messages after a successful import.

    Runs only when the profile's post_process_policy asks for it. Messages are matched
    by their stable Message-ID header so the action is independent of the read run's
    connection. Default policy is a no-op.
    """
    policy = profile.post_process_policy
    if policy is None or (not policy.mark_as_read and not policy.move_to_folder):
        return
    if not internet_message_ids:
        return
    if not password:
        raise ImapProviderError("Mailbox app password secret is not available for post-processing.")

    with _imap_errors("post-processing"), _connect(profile) as mailbox:
        mailbox.login(profile.email_address, password)
        status, _ = mailbox.select(profile.folder)  # read-write for STORE/COPY/EXPUNGE
        if status != "OK":
            raise _folder_open_error(profile)

        moved_any = False
        for message_id in internet_message_ids:
            search_id = message_id if message_id.startswith("<") else f"<{message_id}>"
            # Quote the Message-ID (it can contain IMAP specials) and use UID
            # commands so the ids stay valid even if the mailbox changes mid-loop.
            status, data = mailbox.uid("search", None, "HEADER", "Message-ID", _imap_quote(search_id))
            if status != "OK" or not data or not data[0]:
                continue
            for num in data[0].split():
                if policy.mark_as_read:
                    mailbox.uid("store", num, "+FLAGS", "\\Seen")
                if policy.move_to_folder:
                    copy_status, _ = mailbox.uid("copy", num, policy.move_to_folder)
                    if copy_status == "OK":
                        mailbox.uid("store", num, "+FLAGS", "\\Deleted")
                        moved_any = True
        if moved_any:
            mailbox.expunge()


def _search_mailbox(
    mailbox,
    profile: EmailSourceProfile,
    received_after: datetime | None = None,
    received_before: datetime | None = None,
):
    # Narrow the server-side IMAP search using the retrieval date window plus the
    # source profile's sender allowlist and subject keywords, so only matching
    # candidates are retrieved. Falls back progressively (date-only, then ALL) if
    # the server rejects the narrowed search. Uses UID SEARCH for stable ids.
    date_criteria = _date_criteria(received_after, received_before)
    filter_criteria = _search_criteria(profile.sender_allowlist, profile.subject_contains)
    criteria = date_criteria + filter_criteria if filter_criteria != ["ALL"] else (date_criteria or ["ALL"])
    if criteria != ["ALL"]:
        try:
            status, data = mailbox.uid("search", None, *criteria)
            if status == "OK":
                return status, data
        except imaplib.IMAP4.error:
            pass
        if date_criteria and criteria != date_criteria:
            try:
                status, data = mailbox.uid("search", None, *date_criteria)
                if status == "OK":
                    return status, data
            except imaplib.IMAP4.error:
                pass
    return mailbox.uid("search", None, "ALL")


_IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _imap_date(value: datetime) -> str:
    # RFC 3501 date format with locale-independent English month names.
    utc_value = value.astimezone(UTC)
    return f"{utc_value.day:02d}-{_IMAP_MONTHS[utc_value.month - 1]}-{utc_value.year}"


def _date_criteria(received_after: datetime | None, received_before: datetime | None) -> list[str]:
    # IMAP SINCE/BEFORE compare on INTERNALDATE at day granularity.
    criteria: list[str] = []
    if received_after is not None:
        criteria += ["SINCE", _imap_date(received_after)]
    if received_before is not None:
        criteria += ["BEFORE", _imap_date(received_before)]
    return criteria


def _search_criteria(sender_allowlist, subject_contains) -> list[str]:
    sender_tree = _or_tree("FROM", sender_allowlist)
    subject_tree = _or_tree("SUBJECT", subject_contains)
    if sender_tree and subject_tree:
        # OR the sender and subject matches so either one retrieves a message.
        return ["OR"] + sender_tree + subject_tree
    return sender_tree or subject_tree or ["ALL"]


def _or_tree(key: str, values) -> list[str]:
    # IMAP SEARCH uses prefix OR taking two operands, so fold the values into a
    # nested OR tree: ["OR", FROM, b, FROM, a] means FROM a OR FROM b.
    cleaned = [value.strip() for value in (values or []) if value and value.strip()]
    if not cleaned:
        return []
    tree = [key, _imap_quote(cleaned[0])]
    for value in cleaned[1:]:
        tree = ["OR", key, _imap_quote(value)] + tree
    return tree


def _imap_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _connect(profile: EmailSourceProfile):
    host, port, use_ssl = _imap_endpoint(profile)
    if not use_ssl:
        raise ImapProviderError("IMAP connection must use TLS before mailbox credentials can be sent.")
    _assert_host_allowed(host)
    # NOTE: the SSRF check above resolves the host and imaplib resolves it again
    # here, so a DNS-rebinding attacker controlling the record could in principle
    # swap answers between the two lookups. Accepted residual risk for this
    # deployment; ALLOWED_IMAP_HOSTS pins hosts when stronger guarantees are needed.
    return imaplib.IMAP4_SSL(host, port, timeout=settings.imap_timeout_seconds)


def _assert_host_allowed(host: str) -> None:
    # Prevents the mailbox host from being used as a server-side request forgery
    # primitive (e.g. pointing the connection at cloud metadata or internal
    # services). An explicit allowlist always wins (including over the private
    # range block, so an intentionally allowlisted internal mail host works);
    # otherwise internal/reserved address ranges are blocked unless an operator
    # opts out.
    candidate = host.strip().lower()
    allowlist = [value.strip().lower() for value in settings.allowed_imap_hosts if value.strip()]
    if allowlist:
        if candidate not in allowlist:
            raise ImapProviderError("IMAP host is not in the configured allowlist.")
        return
    if not settings.block_private_imap_hosts:
        return
    try:
        address_infos = socket.getaddrinfo(candidate, None)
    except socket.gaierror as exc:
        raise ImapProviderError("IMAP host could not be resolved.") from exc
    for address_info in address_infos:
        ip_address = ipaddress.ip_address(address_info[4][0])
        if (
            ip_address.is_private
            or ip_address.is_loopback
            or ip_address.is_link_local
            or ip_address.is_reserved
            or ip_address.is_multicast
            or ip_address.is_unspecified
        ):
            raise ImapProviderError("IMAP host resolves to a disallowed internal address.")


def _imap_endpoint(profile: EmailSourceProfile) -> tuple[str, int, bool]:
    # A port embedded in the host ("imap.example.com:993" or "[::1]:993") overrides
    # imap_port. Port 143 is always treated as plaintext IMAP so _connect refuses to
    # send credentials over it; every other port honors the profile's use_ssl flag.
    host = _imap_host(profile).strip()
    configured_port = profile.connection_settings.imap_port or 993
    use_ssl = profile.connection_settings.use_ssl
    host_part, port_part = _split_host_port(host)
    if port_part is not None:
        return host_part, port_part, use_ssl and port_part != 143
    return host_part, configured_port, use_ssl and configured_port != 143


def _split_host_port(host: str) -> tuple[str, int | None]:
    # Bracketed IPv6 literal with port: "[2001:db8::1]:993".
    bracket_match = re.fullmatch(r"\[(?P<host>[^\]]+)\](?::(?P<port>\d+))?", host)
    if bracket_match:
        port_text = bracket_match.group("port")
        return bracket_match.group("host"), int(port_text) if port_text else None
    # "host:port" form; anything with multiple colons is an unbracketed IPv6
    # literal and is returned as-is.
    if host.count(":") == 1:
        host_part, port_part = host.rsplit(":", 1)
        if host_part and port_part.isdigit():
            return host_part.strip(), int(port_part)
    return host, None


def _imap_host(profile: EmailSourceProfile) -> str:
    if profile.connection_settings.imap_host:
        return profile.connection_settings.imap_host.strip()
    host = PROVIDER_HOSTS.get(profile.provider)
    if host:
        return host
    raise ImapProviderError("IMAP host is required for this email provider.")


def _folder_open_error(profile: EmailSourceProfile) -> ImapProviderError:
    folder = profile.folder or "Inbox"
    return ImapProviderError(
        f'IMAP folder "{folder}" could not be opened. Mailbox folder names can be case-sensitive; '
        "check the Email Ingestion profile folder value and use the exact folder name shown by the mailbox provider."
    )


def _to_message_input(profile: EmailSourceProfile, message_id: str, parsed: Message) -> EmailMessageInput:
    subject = parsed.get("subject")
    sender = parsed.get("from") or profile.email_address
    received_at = parsed.get("date") or datetime.now(UTC).isoformat()
    attachments = list(_attachments(parsed))
    return EmailMessageInput(
        message_id=message_id,
        internet_message_id=parsed.get("message-id"),
        sender=sender,
        subject=subject,
        received_at=received_at,
        attachments=attachments,
    )


def _attachments(parsed: Message) -> Iterable[EmailAttachmentInput]:
    for index, part in enumerate(parsed.walk(), start=1):
        filename = part.get_filename()
        if not filename:
            continue
        if PurePath(filename).suffix.lower() != ".pdf":
            continue
        payload = part.get_payload(decode=True) or b""
        if _is_payload_too_large(payload):
            continue
        content_type = part.get_content_type() or "application/octet-stream"
        yield EmailAttachmentInput(
            attachment_id=str(index),
            filename=filename,
            content_type=content_type,
            size_bytes=len(payload),
            content_base64=base64.b64encode(payload).decode("ascii"),
        )


def _is_payload_too_large(payload: bytes) -> bool:
    max_size = settings.max_attachment_size_bytes
    return max_size > 0 and len(payload) > max_size


def _fetch_size_limit() -> int:
    # MIME/base64 encoding adds overhead, so allow a bounded envelope above the
    # attachment cap while still refusing oversized messages before full fetch.
    max_size = settings.max_attachment_size_bytes
    if max_size <= 0:
        return 0
    return int(max_size * 1.4) + 1024 * 1024


def _rfc822_message_size(mailbox, message_id: bytes) -> int | None:
    status, size_data = mailbox.uid("fetch", message_id, "(RFC822.SIZE)")
    if status != "OK":
        return None
    return _rfc822_size(size_data)


def _message_exceeds_fetch_limit(mailbox, message_id: bytes) -> bool:
    fetch_limit = _fetch_size_limit()
    if fetch_limit <= 0:
        return False
    message_size = _rfc822_message_size(mailbox, message_id)
    return message_size is not None and message_size > fetch_limit


def _rfc822_size(size_data) -> int | None:
    for item in size_data or []:
        candidate = item[0] if isinstance(item, tuple) else item
        if isinstance(candidate, bytes):
            match = re.search(rb"RFC822\.SIZE\s+(\d+)", candidate)
            if match:
                return int(match.group(1))
    return None
