"""M1 - User Access Management Start
Provides password hashing and bearer token helpers for Identity Access.
M1 End"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings

PASSWORD_ITERATIONS = 260_000


def _b64encode(data: bytes) -> str:
    """Return URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    """Decode URL-safe base64 without required padding."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-SHA256."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a stored PBKDF2-SHA256 hash."""
    try:
        scheme, iterations, salt, digest = hashed_password.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(_b64encode(candidate), digest)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed bearer token for a user subject."""
    expires_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    header = {"alg": settings.access_token_algorithm, "typ": "JWT"}
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    signing_input = (
        f"{_b64encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = hmac.new(
        settings.access_token_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a signed bearer token."""
    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
        signing_input = f"{header_segment}.{payload_segment}"
        expected_signature = hmac.new(
            settings.access_token_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64encode(expected_signature), signature_segment):
            return None

        payload = json.loads(_b64decode(payload_segment))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


# M1 End
