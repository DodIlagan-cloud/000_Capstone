"""M12 - Email Ingestion Module Start
Protects email ingestion APIs with Stats bearer or internal service auth.
M12 End"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Header, HTTPException, status

from app.config import settings

# Email ingestion manages mailbox credentials and triggers outbound connections,
# so user sessions must carry the admin role. The internal service key is a
# trusted server-to-server caller and is exempt from the role check.
ADMIN_ROLE = "admin"


def require_email_ingestion_auth(
    authorization: str | None = Header(default=None),
    internal_api_key: str | None = Header(default=None, alias="X-Stats-Internal-Key"),
) -> None:
    if _valid_internal_key(internal_api_key):
        return
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[len("Bearer ") :].strip()
        payload = _decode_access_token(token)
        if payload:
            if payload.get("role") != ADMIN_ROLE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email ingestion requires an administrator account.",
                )
            return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")


def _valid_internal_key(value: str | None) -> bool:
    expected = settings.stats_internal_api_key
    if not expected or not value:
        return False
    return hmac.compare_digest(value, expected)


def _decode_access_token(token: str) -> dict[str, Any] | None:
    # NOTE: This mirrors identity-access-module/app/utils/security.decode_access_token.
    # The two run in separate processes and cannot share a package, so any change to
    # token format, algorithm, or claims must be made in BOTH places or tokens will
    # silently fail to validate here. Only the algorithm/signature/sub/exp are checked;
    # any token signed with the shared ACCESS_TOKEN_SECRET_KEY is accepted, so do not
    # reuse that key to sign tokens for other purposes.
    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
        header = json.loads(_b64decode(header_segment))
        if header.get("alg") != settings.access_token_algorithm:
            return None
        signing_input = f"{header_segment}.{payload_segment}"
        expected_signature = hmac.new(
            settings.access_token_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64encode(expected_signature), signature_segment):
            return None
        payload = json.loads(_b64decode(payload_segment))
        if not payload.get("sub"):
            return None
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
