"""M12 - Email Ingestion Module Start
Provides generic IMAP provider adapters behind the M12 contract.
M12 End"""

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

    with _connect(profile) as mailbox:
        mailbox.login(profile.email_address, password)
        status, _ = mailbox.select(profile.folder, readonly=True)
        if status != "OK":
            raise _folder_open_error(profile)


def fetch_messages(profile: EmailSourceProfile, password: str | None, max_messages: int | None) -> list[EmailMessageInput]:
    if not password:
        raise ImapProviderError("Mailbox app password secret is not available.")

    with _connect(profile) as mailbox:
        mailbox.login(profile.email_address, password)
        status, _ = mailbox.select(profile.folder, readonly=True)
        if status != "OK":
            raise _folder_open_error(profile)

        status, search_data = _search_mailbox(mailbox, profile)
        if status != "OK":
            raise ImapProviderError("IMAP message search failed.")

        message_ids = search_data[0].split()
        if max_messages and max_messages > 0:
            message_ids = message_ids[-max_messages:]
        messages: list[EmailMessageInput] = []
        for message_id in message_ids:
            if _message_exceeds_fetch_limit(mailbox, message_id):
                continue
            status, fetch_data = mailbox.fetch(message_id, "(RFC822)")
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


def _search_mailbox(mailbox, profile: EmailSourceProfile):
    # Narrow the server-side IMAP search using the source profile's sender
    # allowlist and subject keywords so only matching candidates are retrieved.
    # Falls back to scanning ALL messages if the narrowed search is rejected.
    criteria = _search_criteria(profile.sender_allowlist, profile.subject_contains)
    if criteria != ["ALL"]:
        try:
            status, data = mailbox.search(None, *criteria)
            if status == "OK":
                return status, data
        except imaplib.IMAP4.error:
            pass
    return mailbox.search(None, "ALL")


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
    return imaplib.IMAP4_SSL(host, port)


def _assert_host_allowed(host: str) -> None:
    # Prevents the mailbox host from being used as a server-side request forgery
    # primitive (e.g. pointing the connection at cloud metadata or internal
    # services). An explicit allowlist always wins; otherwise internal/reserved
    # address ranges are blocked unless an operator opts out.
    candidate = host.strip().lower()
    allowlist = [value.strip().lower() for value in settings.allowed_imap_hosts if value.strip()]
    if allowlist and candidate not in allowlist:
        raise ImapProviderError("IMAP host is not in the configured allowlist.")
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
    host = _imap_host(profile).strip()
    configured_port = profile.connection_settings.imap_port or 993
    if host.count(":") == 1:
        host_part, port_part = host.rsplit(":", 1)
        if host_part and port_part.isdigit():
            port = int(port_part)
            return host_part.strip(), port, port != 143
    return host, configured_port, profile.connection_settings.use_ssl and configured_port != 143


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


def _message_exceeds_fetch_limit(mailbox, message_id: bytes) -> bool:
    max_size = settings.max_attachment_size_bytes
    if max_size <= 0:
        return False
    status, size_data = mailbox.fetch(message_id, "(RFC822.SIZE)")
    if status != "OK":
        return False
    message_size = _rfc822_size(size_data)
    if message_size is None:
        return False
    # MIME/base64 encoding adds overhead, so allow a bounded envelope above the
    # attachment cap while still refusing oversized messages before full fetch.
    fetch_limit = int(max_size * 1.4) + 1024 * 1024
    return message_size > fetch_limit


def _rfc822_size(size_data) -> int | None:
    for item in size_data or []:
        candidate = item[0] if isinstance(item, tuple) else item
        if isinstance(candidate, bytes):
            match = re.search(rb"RFC822\.SIZE\s+(\d+)", candidate)
            if match:
                return int(match.group(1))
    return None
