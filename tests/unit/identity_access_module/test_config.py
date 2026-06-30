"""M1 - User Access Management Start
Verifies security-sensitive Identity Access configuration guards.
M1 End"""

import pytest

from app.config import Settings


def test_placeholder_access_token_secret_is_rejected_when_debug_false(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET_KEY", "development-only-change-me")

    with pytest.raises(RuntimeError, match="ACCESS_TOKEN_SECRET_KEY must be overridden"):
        Settings()


def test_short_access_token_secret_is_rejected_when_debug_false(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET_KEY", "too-short")

    with pytest.raises(RuntimeError, match="ACCESS_TOKEN_SECRET_KEY must be overridden"):
        Settings()


# M1 End
