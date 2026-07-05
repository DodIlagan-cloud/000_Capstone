"""M12 - Email Ingestion Module Start
Tests the automated email attachment pathway.
M12 End"""

import base64
import hashlib
import logging
from email.message import EmailMessage

import pytest


def test_health_endpoint_reports_provider_and_mode(client):
    response = client.get("/health")

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["service"] == "Email Ingestion Module"
    assert payload["provider"] == "synthetic"
    assert payload["mode"] == "dry_run"


def test_email_ingestion_sources_require_authentication(unauthenticated_client):
    response = unauthenticated_client.get("/api/v1/email-ingestion-sources")

    assert response.status_code == 401


def test_email_ingestion_runs_require_authentication(unauthenticated_client, email_payload):
    response = unauthenticated_client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    assert response.status_code == 401


def test_email_ingestion_routes_accept_internal_api_key(unauthenticated_client):
    response = unauthenticated_client.get(
        "/api/v1/email-ingestion-sources",
        headers={"X-Stats-Internal-Key": "m12-test-internal-api-key"},
    )

    assert response.status_code == 200


def test_sql_backed_email_secrets_require_dedicated_encryption_key_when_debug_false(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("EMAIL_SECRET_PROVIDER", "azure_sql")
    monkeypatch.setenv("EMAIL_SECRET_ENCRYPTION_KEY", "")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET_KEY", "access-token-secret-key-with-32-plus-chars")

    with pytest.raises(RuntimeError, match="EMAIL_SECRET_ENCRYPTION_KEY must be set"):
        Settings()


def test_email_secret_encryption_can_fallback_to_access_token_key_only_in_debug(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("EMAIL_SECRET_PROVIDER", "azure_sql")
    monkeypatch.setenv("EMAIL_SECRET_ENCRYPTION_KEY", "")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET_KEY", "local-debug-fallback-key-with-32-plus-chars")

    settings = Settings()

    assert settings.email_secret_encryption_key == "local-debug-fallback-key-with-32-plus-chars"


def test_automated_run_returns_retrieved_candidate_for_allowed_pdf(client, email_payload):
    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["summary"]["message_count"] == 1
    assert payload["summary"]["attachment_count"] == 1
    assert payload["summary"]["retrieved_count"] == 1
    assert payload["candidates"][0]["status"] == "retrieved"
    assert payload["candidates"][0]["source"]["subject_redacted"] == "[redacted]"
    assert payload["candidates"][0]["sha256"]


def test_automated_run_records_no_attachment_finding(client, email_payload):
    email_payload["messages"][0]["attachments"] = []

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["summary"]["attachment_count"] == 0
    assert payload["evaluation"]["finding_counts"]["info"] == 1
    assert payload["findings"][0]["code"] == "EMAIL_NO_ATTACHMENTS"


def test_automated_run_skips_unsupported_attachment(client, email_payload):
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["filename"] = "statement.exe"
    attachment["content_type"] = "application/octet-stream"

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()
    codes = {finding["code"] for finding in payload["candidates"][0]["findings"]}

    assert response.status_code == 200
    assert payload["status"] == "completed_with_warnings"
    assert payload["summary"]["skipped_count"] == 1
    assert "UNSUPPORTED_ATTACHMENT_EXTENSION" in codes
    assert "UNSUPPORTED_ATTACHMENT_MIME_TYPE" in codes


def test_automated_run_accepts_pdf_with_generic_mail_mime_type(client, email_payload):
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["filename"] = "BPI eStatement Apr 2026.pdf"
    attachment["content_type"] = "application/octet-stream"

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["summary"]["retrieved_count"] == 1
    assert payload["candidates"][0]["status"] == "retrieved"
    assert payload["candidates"][0]["findings"] == []


def test_automated_run_uses_source_sender_and_subject_filters(client, email_payload):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "mailbox-primary",
            "display_name": "Credit Cards",
            "provider": "custom_imap",
            "email_address": "finance@example.com",
            "folder": "Inbox",
            "sender_allowlist": ["creditcardstatement@mail.hsbc.com.ph"],
            "subject_contains": ["HSBC GOLD VISA e-Statement"],
        },
    )
    email_payload["messages"][0]["sender"] = "alerts@example.test"
    email_payload["messages"][0]["subject"] = "Unrelated notice"
    matching_content = b"%PDF-1.4\nmatching statement\n%%EOF"
    email_payload["messages"].append(
        {
            "message_id": "message-002",
            "internet_message_id": "<message-002@example.test>",
            "sender": "Credit Cards <creditcardstatement@mail.hsbc.com.ph>",
            "subject": "HSBC GOLD VISA e-Statement for June",
            "received_at": "2026-06-18T08:30:00Z",
            "attachments": [
                {
                    "attachment_id": "attachment-002",
                    "filename": "hsbc-statement.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(matching_content),
                    "content_base64": base64.b64encode(matching_content).decode("ascii"),
                }
            ],
        }
    )

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["message_count"] == 1
    assert payload["summary"]["attachment_count"] == 1
    assert payload["candidates"][0]["source"]["message_id"] == "message-002"
    assert payload["candidates"][0]["source"]["sender"] == "Credit Cards <creditcardstatement@mail.hsbc.com.ph>"


def test_automated_run_allows_unlimited_synthetic_messages(client, email_payload):
    pdf = b"%PDF-1.4\nstatement\n%%EOF"
    b64 = base64.b64encode(pdf).decode("ascii")
    email_payload["retrieval"]["max_messages"] = 0
    email_payload["messages"] = [
        {
            "message_id": f"message-{index:03d}",
            "sender": "statements@example.test",
            "subject": "Statement",
            "received_at": "2026-06-18T08:30:00Z",
            "attachments": [
                {
                    "attachment_id": f"attachment-{index:03d}",
                    "filename": f"statement-{index:03d}.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(pdf),
                    "content_base64": b64,
                }
            ],
        }
        for index in range(1, 31)
    ]

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["message_count"] == 30
    assert payload["summary"]["attachment_count"] == 30


def test_automated_run_marks_duplicate_attachment(client, email_payload):
    message = email_payload["messages"][0]
    message["attachments"].append(dict(message["attachments"][0]))

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed_with_warnings"
    assert payload["summary"]["retrieved_count"] == 1
    assert payload["summary"]["duplicate_count"] == 1
    assert payload["candidates"][1]["status"] == "duplicate"


def test_handoff_to_file_ingestion_maps_queued_response(run_ingestion_func, ingestion_request_cls, email_payload, monkeypatch):
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False
    request = ingestion_request_cls(**email_payload)
    captured = {}

    class FakeResponse:
        is_success = True
        status_code = 200

        @staticmethod
        def json():
            return {
                "ingestion_id": "ingest_email_001",
                "status": "queued",
                "handoff": {"content_reference": "storage://email/statement.pdf"},
            }

    def fake_post(*_args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return FakeResponse()

    monkeypatch.setattr(run_ingestion_func.__globals__["settings"], "stats_internal_api_key", "internal-api-key")
    monkeypatch.setattr(run_ingestion_func.__globals__["httpx"], "post", fake_post)

    result = run_ingestion_func(request)

    assert result.status == "completed"
    assert result.summary.handed_off_count == 1
    assert result.candidates[0].status == "handed_off"
    assert result.candidates[0].handoff.ingestion_id == "ingest_email_001"
    assert captured["headers"] == {"X-Stats-Internal-Key": "internal-api-key"}


def test_handoff_logs_trace_ids_without_secret_values(
    run_ingestion_func,
    ingestion_request_cls,
    email_payload,
    monkeypatch,
    caplog,
):
    email_payload["source_id"] = "trace-mailbox"
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False
    email_payload["messages"][0]["message_id"] = "message-trace-001"
    email_payload["messages"][0]["attachments"][0]["attachment_id"] = "attachment-trace-001"
    email_payload["messages"][0]["attachments"][0]["filename"] = "trace-statement.pdf"
    email_payload["messages"][0]["attachments"][0]["content_base64"] = base64.b64encode(
        b"%PDF-1.4\ntraceable statement\n%%EOF"
    ).decode("ascii")
    request = ingestion_request_cls(**email_payload)

    class FakeResponse:
        is_success = True
        status_code = 200

        @staticmethod
        def json():
            return {
                "ingestion_id": "ingest_trace_001",
                "status": "queued",
                "handoff": {
                    "content_reference": "azure-blob://ststatsdev001/stats-documents/intake/ingest_trace_001/trace-statement.pdf"
                },
            }

    monkeypatch.setattr("app.services.ingestion_service.httpx.post", lambda *_args, **_kwargs: FakeResponse())

    with caplog.at_level(logging.INFO, logger="app.services.ingestion_service"):
        result = run_ingestion_func(request)

    log_text = "\n".join(record.getMessage() for record in caplog.records)

    assert result.candidates[0].status == "handed_off"
    assert "M12 email attachment handoff completed." in log_text
    assert result.run_id in log_text
    assert "trace-mailbox" in log_text
    assert "message-trace-001" in log_text
    assert "attachment-trace-001" in log_text
    assert "trace-mailbox:message-trace-001:attachment-trace-001" in log_text
    assert "ingest_trace_001" in log_text
    assert "azure-blob://ststatsdev001/stats-documents/intake/ingest_trace_001/trace-statement.pdf" in log_text
    assert "app-password" not in log_text
    assert "password" not in log_text.lower()


def test_create_source_profile_keeps_app_password_out_of_response(client):
    response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "bank-mailbox",
            "display_name": "Bank Mailbox",
            "provider": "custom_imap",
            "email_address": "bank-mailbox@example.com",
            "folder": "Statements",
            "app_password": "not-returned",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["source_id"] == "bank-mailbox"
    assert payload["provider"] == "custom_imap"
    assert payload["secret_ref"] == "stats-email-custom-imap-app-password-bank-mailbox"
    assert "app_password" not in payload

    list_response = client.get("/api/v1/email-ingestion-sources")
    assert list_response.status_code == 200
    assert list_response.json()["sources"][0]["source_id"] == "bank-mailbox"
    assert "app_password" not in list_response.text


def test_test_connection_returns_connected_when_imap_adapter_succeeds(client, monkeypatch):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "connected-mailbox",
            "display_name": "Connected Mailbox",
            "provider": "gmail_imap",
            "email_address": "connected@example.com",
            "folder": "Inbox",
            "secret_ref": "stats-email-gmail-imap-app-password-connected-mailbox",
        },
    )

    def fake_test_connection(_profile, password):
        assert password == "one-time-test-password"
        assert _profile.folder == "Archive"

    monkeypatch.setattr("app.routes.sources.test_connection", fake_test_connection)

    response = client.post(
        "/api/v1/email-ingestion-sources/connected-mailbox/test-connection",
        json={"app_password": "one-time-test-password", "folder": "Archive"},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "connected"
    assert payload["folder"] == "Archive"


def test_saved_app_password_is_resolved_from_secret_reference(client, monkeypatch):
    create_response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "saved-mailbox",
            "display_name": "Saved Mailbox",
            "provider": "outlook_imap",
            "email_address": "saved@example.com",
            "folder": "Inbox",
            "app_password": "saved-app-password",
        },
    )
    assert create_response.status_code == 200
    assert "saved-app-password" not in create_response.text

    def fake_test_connection(_profile, password):
        assert password == "saved-app-password"

    monkeypatch.setattr("app.routes.sources.test_connection", fake_test_connection)

    response = client.post(
        "/api/v1/email-ingestion-sources/saved-mailbox/test-connection",
        json={},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    assert "saved-app-password" not in response.text


def test_custom_imap_source_persists_connection_settings(client):
    response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "custom-mailbox",
            "display_name": "Custom Mailbox",
            "provider": "custom_imap",
            "email_address": "finance@example.com",
            "folder": "Statements",
            "connection_settings": {
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "use_ssl": True,
            },
            "app_password": "custom-app-password",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "custom_imap"
    assert payload["secret_ref"] == "stats-email-custom-imap-app-password-custom-mailbox"
    assert payload["connection_settings"]["imap_host"] == "imap.example.com"
    assert "custom-app-password" not in response.text


def test_key_vault_secret_provider_stores_normalized_secret_reference(monkeypatch):
    from app.services import secret_service

    stored = {}

    class FakeSecret:
        value = "stored-app-password"

    class FakeSecretClient:
        def set_secret(self, name, value):
            stored[name] = value

        def get_secret(self, name):
            assert name == "stats-email-gmail-app-password"
            return FakeSecret()

    monkeypatch.setattr(secret_service.settings, "email_secret_provider", "azure_key_vault")
    monkeypatch.setattr(secret_service.settings, "email_key_vault_url", "https://stats-kv.vault.azure.net/")
    monkeypatch.setattr(secret_service, "_key_vault_secret_client", lambda: FakeSecretClient())

    secret_service.store_secret("stats-email-gmail-app-password", "stored-app-password")
    resolved = secret_service.resolve_secret("stats-email-gmail-app-password")

    assert stored == {"stats-email-gmail-app-password": "stored-app-password"}
    assert resolved == "stored-app-password"


def test_secret_ref_environment_lookup_is_namespaced(monkeypatch):
    from app.services import secret_service

    monkeypatch.setattr(secret_service.settings, "email_secret_provider", "environment")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET_KEY", "must-not-resolve")
    monkeypatch.setenv("STATS_EMAIL_SECRET_STATS_EMAIL_GMAIL_APP_PASSWORD", "allowed-env-secret")

    assert secret_service.resolve_secret("access-token-secret-key") is None
    assert secret_service.resolve_secret("stats-email-gmail-app-password") == "allowed-env-secret"


def test_secret_ref_normalization_avoids_punctuation_collisions():
    from app.services.secret_service import normalize_secret_ref

    assert normalize_secret_ref("stats-email-gmail-app-password") == "stats-email-gmail-app-password"
    assert normalize_secret_ref("Stats_Email_Gmail_App_Password") != normalize_secret_ref("Stats-Email-Gmail-App-Password")


def test_automated_run_fetches_messages_for_imap_source_profile(client, monkeypatch):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "fetch-mailbox",
            "display_name": "Fetch Mailbox",
            "provider": "gmail_imap",
            "email_address": "fetch@example.com",
            "folder": "Statements",
            "secret_ref": "stats-email-gmail-imap-app-password-fetch-mailbox",
        },
    )

    content = b"%PDF-1.4\nsynthetic email statement\n%%EOF"

    def fake_resolve_secret(secret_ref):
        assert secret_ref == "stats-email-gmail-imap-app-password-fetch-mailbox"
        return "resolved-app-password"

    def fake_fetch_messages(profile, password, max_messages, **kwargs):
        assert profile.source_id == "fetch-mailbox"
        assert profile.folder == "Statements"
        assert password == "resolved-app-password"
        assert max_messages == 25
        # The default lookback window must reach the IMAP fetch as received_after.
        assert kwargs.get("received_after") is not None
        from app.models.ingestion import EmailAttachmentInput, EmailMessageInput

        return [
            EmailMessageInput(
                message_id="imap-001",
                sender="statements@example.test",
                subject="Statement",
                received_at="2026-06-18T01:00:00Z",
                attachments=[
                    EmailAttachmentInput(
                        attachment_id="1",
                        filename="statement.pdf",
                        content_type="application/pdf",
                        size_bytes=len(content),
                        content_base64=base64.b64encode(content).decode("ascii"),
                    )
                ],
            )
        ]

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", fake_resolve_secret)
    monkeypatch.setattr("app.services.ingestion_service.fetch_messages", fake_fetch_messages)

    response = client.post(
        "/api/v1/email-ingestions/automated-runs",
        json={
            "source_id": "fetch-mailbox",
            "policy": {"dry_run": True},
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["provider"] == "gmail_imap"
    assert payload["folder"] == "Statements"
    assert payload["summary"]["retrieved_count"] == 1


def test_automated_run_reports_actionable_folder_error_for_imap_source(client, monkeypatch):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "case-sensitive-folder",
            "display_name": "Case Sensitive Folder",
            "provider": "gmail_imap",
            "email_address": "fetch@example.com",
            "folder": "Inbox",
            "secret_ref": "stats-email-gmail-imap-app-password-case-sensitive-folder",
        },
    )

    from app.services.imap_service import ImapProviderError

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", lambda _secret_ref: "resolved-app-password")
    monkeypatch.setattr(
        "app.services.ingestion_service.fetch_messages",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ImapProviderError(
                'IMAP folder "inbox" could not be opened. Mailbox folder names can be case-sensitive; '
                "check the Email Ingestion profile folder value and use the exact folder name shown by the mailbox provider."
            )
        ),
    )

    response = client.post(
        "/api/v1/email-ingestions/automated-runs",
        json={
            "source_id": "case-sensitive-folder",
            "retrieval": {"mailbox_folder": "inbox"},
            "policy": {"dry_run": True},
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "MAILBOX_RETRIEVAL_FAILED"
    assert 'IMAP folder "inbox" could not be opened' in payload["findings"][0]["message"]
    assert "case-sensitive" in payload["findings"][0]["message"]
    assert "Email Ingestion profile folder value" in payload["findings"][0]["message"]


def test_automated_run_uses_requested_mailbox_folder_for_imap_fetch(client, monkeypatch):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "fetch-folder",
            "display_name": "Fetch Folder",
            "provider": "gmail_imap",
            "email_address": "fetch@example.com",
            "folder": "Inbox",
            "secret_ref": "stats-email-gmail-imap-app-password-fetch-folder",
        },
    )

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", lambda _secret_ref: "resolved-app-password")

    def fake_fetch_messages(profile, _password, _max_messages, **_kwargs):
        assert profile.folder == "Statements"
        return []

    monkeypatch.setattr("app.services.ingestion_service.fetch_messages", fake_fetch_messages)

    response = client.post(
        "/api/v1/email-ingestions/automated-runs",
        json={
            "source_id": "fetch-folder",
            "retrieval": {"mailbox_folder": "Statements"},
            "policy": {"dry_run": True},
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["folder"] == "Statements"


def test_automated_run_passes_unlimited_to_imap_fetch(client, monkeypatch):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "fetch-unlimited",
            "display_name": "Fetch Unlimited",
            "provider": "gmail_imap",
            "email_address": "fetch@example.com",
            "folder": "Statements",
            "secret_ref": "stats-email-gmail-imap-app-password-fetch-unlimited",
        },
    )

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", lambda _secret_ref: "resolved-app-password")

    def fake_fetch_messages(_profile, _password, max_messages, **_kwargs):
        assert max_messages == 0
        return []

    monkeypatch.setattr("app.services.ingestion_service.fetch_messages", fake_fetch_messages)

    response = client.post(
        "/api/v1/email-ingestions/automated-runs",
        json={
            "source_id": "fetch-unlimited",
            "retrieval": {"max_messages": 0},
            "policy": {"dry_run": True},
        },
    )

    assert response.status_code == 200


def test_password_protected_pdf_is_blocked_before_handoff(client, email_payload):
    encrypted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Encrypt 5 0 R >>\nendobj\n%%EOF"
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["content_base64"] = base64.b64encode(encrypted_pdf).decode("ascii")
    attachment["size_bytes"] = len(encrypted_pdf)
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert payload["summary"]["password_required_count"] == 1
    assert payload["summary"]["handed_off_count"] == 0
    assert payload["candidates"][0]["status"] == "password_required"
    assert payload["candidates"][0]["password_state"] == "password_required"
    assert payload["candidates"][0]["findings"][0]["code"] == "PDF_PASSWORD_REQUIRED"


def test_password_protected_pdf_marker_after_header_is_blocked(client, email_payload, monkeypatch):
    monkeypatch.setattr("app.services.ingestion_service._unlock_pdf", lambda _content_base64, _password: None)
    encrypted_pdf = b"%PDF-1.7\n" + (b"0" * 5000) + b"\ntrailer\n<< /Encrypt 5 0 R >>\n%%EOF"
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["content_base64"] = base64.b64encode(encrypted_pdf).decode("ascii")
    attachment["size_bytes"] = len(encrypted_pdf)
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert payload["summary"]["password_required_count"] == 1
    assert payload["summary"]["handed_off_count"] == 0
    assert payload["candidates"][0]["status"] == "password_required"
    assert payload["candidates"][0]["findings"][0]["code"] == "PDF_PASSWORD_REQUIRED"


def _create_utilities_rules_source(client):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "mailbox-primary",
            "display_name": "Primary Mailbox",
            "provider": "custom_imap",
            "email_address": "finance@example.com",
            "folder": "Inbox",
            "pdf_password_policy": {
                "default_action": "use_source_secret",
                "password_rules": [
                    {
                        "rule_id": "utilities",
                        "display_name": "Utilities",
                        "password_secret_ref": "stats-pdf-password-utilities",
                    },
                    {
                        "rule_id": "insurance",
                        "display_name": "Insurance",
                        "password_secret_ref": "stats-pdf-password-insurance",
                    },
                    {
                        "rule_id": "rates",
                        "display_name": "Council Rates",
                        "password_secret_ref": "stats-pdf-password-rates",
                    },
                ],
            },
        },
    )


def _apply_encrypted_pdf(email_payload):
    encrypted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Encrypt 5 0 R >>\nendobj\n%%EOF"
    email_payload["messages"][0]["subject"] = "Electricity bill"
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["filename"] = "power-bill.pdf"
    attachment["content_base64"] = base64.b64encode(encrypted_pdf).decode("ascii")
    attachment["size_bytes"] = len(encrypted_pdf)


def test_password_protected_pdf_unlocked_by_saved_password(client, email_payload, monkeypatch):
    _create_utilities_rules_source(client)
    _apply_encrypted_pdf(email_payload)

    tried_passwords = []

    def fake_resolve_secret(secret_ref):
        return f"resolved-{secret_ref}"

    def fake_unlock(_content_base64, password):
        tried_passwords.append(password)
        if password == "resolved-stats-pdf-password-insurance":
            return b"%PDF-1.7\nunlocked statement\n%%EOF"
        return None

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", fake_resolve_secret)
    monkeypatch.setattr(
        "app.services.ingestion_service._unlock_pdf",
        fake_unlock,
    )

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    # Dry run: the rule-matched PDF is unlocked, not blocked.
    assert payload["status"] == "completed"
    assert payload["candidates"][0]["status"] == "unlocked"
    assert payload["candidates"][0]["password_state"] == "unlocked"
    assert payload["candidates"][0]["password_rule_id"] == "insurance"
    assert payload["candidates"][0]["password_secret_ref"] == "stats-pdf-password-insurance"
    assert payload["candidates"][0]["findings"][0]["code"] == "PDF_PASSWORD_UNLOCKED"
    assert tried_passwords == [
        "resolved-stats-pdf-password-utilities",
        "resolved-stats-pdf-password-insurance",
    ]
    assert payload["summary"]["password_required_count"] == 0


def test_unlocked_pdf_is_handed_off_with_decrypted_content(client, email_payload, monkeypatch):
    _create_utilities_rules_source(client)
    _apply_encrypted_pdf(email_payload)
    unlocked_bytes = b"%PDF-1.7\nunlocked statement bytes\n%%EOF"
    monkeypatch.setattr(
        "app.services.ingestion_service._unlock_pdf",
        lambda content_base64, password: unlocked_bytes,
    )

    captured = {}

    class FakeResponse:
        is_success = True
        status_code = 200

        @staticmethod
        def json():
            return {
                "ingestion_id": "ingest_email_unlocked",
                "status": "queued",
                "handoff": {"content_reference": "storage://email/unlocked.pdf"},
            }

    def fake_post(*_args, **kwargs):
        captured["files"] = kwargs.get("files")
        captured["data"] = kwargs.get("data")
        return FakeResponse()

    monkeypatch.setattr("app.services.ingestion_service.httpx.post", fake_post)

    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["candidates"][0]["status"] == "handed_off"
    assert payload["candidates"][0]["password_state"] == "unlocked"
    assert payload["candidates"][0]["handoff"]["ingestion_id"] == "ingest_email_unlocked"
    assert payload["summary"]["handed_off_count"] == 1
    # The decrypted bytes (not the encrypted original) are handed off, with a matching hash.
    assert captured["files"]["file"][1] == unlocked_bytes
    assert captured["data"]["validation_sha256"] == hashlib.sha256(unlocked_bytes).hexdigest()
    # Provenance: the candidate's sha256 matches the stored (decrypted) content so
    # run history lines up with Blob/intake evidence; the encrypted-source hash is
    # preserved separately.
    encrypted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Encrypt 5 0 R >>\nendobj\n%%EOF"
    assert payload["candidates"][0]["sha256"] == hashlib.sha256(unlocked_bytes).hexdigest()
    assert payload["candidates"][0]["original_sha256"] == hashlib.sha256(encrypted_pdf).hexdigest()


def test_matched_rule_marks_password_failed_when_unlock_fails(client, email_payload, monkeypatch):
    _create_utilities_rules_source(client)
    _apply_encrypted_pdf(email_payload)
    monkeypatch.setattr(
        "app.services.ingestion_service._unlock_pdf",
        lambda content_base64, password: None,
    )
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False

    response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed_with_warnings"
    assert payload["candidates"][0]["status"] == "password_failed"
    assert payload["candidates"][0]["password_state"] == "password_failed"
    assert payload["candidates"][0]["password_rule_id"] is None
    assert payload["candidates"][0]["findings"][0]["code"] == "PDF_PASSWORD_FAILED"
    assert payload["summary"]["handed_off_count"] == 0


def test_update_source_profile_round_trips_multiple_password_rules(client):
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "rules-mailbox",
            "display_name": "Rules Mailbox",
            "provider": "custom_imap",
            "email_address": "finance@example.com",
            "folder": "Inbox",
        },
    )

    patch_response = client.patch(
        "/api/v1/email-ingestion-sources/rules-mailbox",
        json={
            "folder": "Statements",
            "connection_settings": {
                "imap_host": "imap.example.com",
                "imap_port": 994,
                "use_ssl": True,
            },
            "pdf_password_policy": {
                "default_action": "use_source_secret",
                "password_rules": [
                    {
                        "rule_id": "utilities",
                        "display_name": "Utilities",
                        "password_secret_ref": "stats-pdf-password-utilities",
                        "password": "utilities-password",
                    },
                    {
                        "rule_id": "insurance",
                        "display_name": "Insurance",
                        "password_secret_ref": "stats-pdf-password-insurance",
                        "password": "insurance-password",
                    },
                ],
            },
        },
    )

    payload = patch_response.json()

    assert patch_response.status_code == 200
    assert "utilities-password" not in patch_response.text
    assert "insurance-password" not in patch_response.text
    # Updated values are persisted.
    assert payload["folder"] == "Statements"
    assert payload["connection_settings"]["imap_host"] == "imap.example.com"
    assert payload["connection_settings"]["imap_port"] == 994
    # Both saved password references round-trip in their configured order.
    rules = payload["pdf_password_policy"]["password_rules"]
    assert [rule["rule_id"] for rule in rules] == ["utilities", "insurance"]
    assert [rule["password_secret_ref"] for rule in rules] == [
        "stats-pdf-password-utilities",
        "stats-pdf-password-insurance",
    ]
    # Untouched create-time values are preserved.
    assert payload["display_name"] == "Rules Mailbox"
    assert payload["provider"] == "custom_imap"

    from app.services.secret_service import resolve_secret

    assert resolve_secret("stats-pdf-password-utilities") == "utilities-password"
    assert resolve_secret("stats-pdf-password-insurance") == "insurance-password"

    # A follow-up GET reflects the same persisted rules (store consistency).
    listed = client.get("/api/v1/email-ingestion-sources").json()["sources"]
    stored = next(item for item in listed if item["source_id"] == "rules-mailbox")
    assert len(stored["pdf_password_policy"]["password_rules"]) == 2
    assert stored["folder"] == "Statements"


def test_same_mailbox_supports_multiple_profiles_with_distinct_filters(client):
    shared_email = "household@example.com"

    bills_response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "household-bills",
            "display_name": "Household Bills",
            "provider": "custom_imap",
            "email_address": shared_email,
            "folder": "Bills",
            "subject_contains": ["bill", "statement"],
            "pdf_password_policy": {
                "password_rules": [
                    {
                        "rule_id": "utilities",
                        "display_name": "Utilities",
                        "password_secret_ref": "stats-pdf-password-utilities",
                    }
                ],
            },
        },
    )
    receipts_response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "household-receipts",
            "display_name": "Household Receipts",
            "provider": "custom_imap",
            "email_address": shared_email,
            "folder": "Receipts",
            "subject_contains": ["receipt"],
            "pdf_password_policy": {
                "password_rules": [
                    {
                        "rule_id": "insurance",
                        "display_name": "Insurance",
                        "password_secret_ref": "stats-pdf-password-insurance",
                    }
                ],
            },
        },
    )

    assert bills_response.status_code == 200
    assert receipts_response.status_code == 200

    listed = client.get("/api/v1/email-ingestion-sources").json()["sources"]
    by_id = {item["source_id"]: item for item in listed}

    # Two independent profiles exist for the same mailbox address.
    assert by_id["household-bills"]["email_address"] == shared_email
    assert by_id["household-receipts"]["email_address"] == shared_email
    # Each keeps its own folder, filters, and password rule without bleed-through.
    assert by_id["household-bills"]["folder"] == "Bills"
    assert by_id["household-receipts"]["folder"] == "Receipts"
    assert by_id["household-bills"]["subject_contains"] == ["bill", "statement"]
    assert by_id["household-receipts"]["subject_contains"] == ["receipt"]
    assert by_id["household-bills"]["pdf_password_policy"]["password_rules"][0]["rule_id"] == "utilities"
    assert by_id["household-receipts"]["pdf_password_policy"]["password_rules"][0]["rule_id"] == "insurance"


def test_same_mailbox_profiles_use_their_own_saved_passwords(client, email_payload, monkeypatch):
    shared_email = "household@example.com"
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "utilities-profile",
            "display_name": "Utilities Profile",
            "provider": "custom_imap",
            "email_address": shared_email,
            "folder": "Bills",
            "pdf_password_policy": {
                "password_rules": [
                    {
                        "rule_id": "utilities",
                        "display_name": "Utilities",
                        "password_secret_ref": "stats-pdf-password-utilities",
                    }
                ],
            },
        },
    )
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "insurance-profile",
            "display_name": "Insurance Profile",
            "provider": "custom_imap",
            "email_address": shared_email,
            "folder": "Bills",
            "pdf_password_policy": {
                "password_rules": [
                    {
                        "rule_id": "insurance",
                        "display_name": "Insurance",
                        "password_secret_ref": "stats-pdf-password-insurance",
                    }
                ],
            },
        },
    )

    encrypted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Encrypt 5 0 R >>\nendobj\n%%EOF"
    email_payload["messages"][0]["subject"] = "Electricity bill"
    attachment = email_payload["messages"][0]["attachments"][0]
    attachment["content_base64"] = base64.b64encode(encrypted_pdf).decode("ascii")
    attachment["size_bytes"] = len(encrypted_pdf)

    def fake_resolve_secret(secret_ref):
        return f"resolved-{secret_ref}"

    def fake_unlock(_content_base64, password):
        if password == "resolved-stats-pdf-password-utilities":
            return b"%PDF-1.7\nunlocked statement\n%%EOF"
        return None

    monkeypatch.setattr("app.services.ingestion_service.resolve_secret", fake_resolve_secret)
    monkeypatch.setattr("app.services.ingestion_service._unlock_pdf", fake_unlock)

    # The same encrypted email tries only the saved passwords belonging to the targeted profile.
    email_payload["source_id"] = "utilities-profile"
    utilities = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload).json()
    assert utilities["candidates"][0]["password_rule_id"] == "utilities"
    assert utilities["candidates"][0]["password_secret_ref"] == "stats-pdf-password-utilities"

    # Routed at the insurance profile, only the insurance saved password is tried.
    email_payload["source_id"] = "insurance-profile"
    insurance = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload).json()
    assert insurance["candidates"][0]["status"] == "password_failed"
    assert insurance["candidates"][0]["password_rule_id"] is None
    assert insurance["candidates"][0]["findings"][0]["code"] == "PDF_PASSWORD_FAILED"


def test_imap_search_criteria_uses_sender_and_subject():
    from app.services import imap_service

    # No filters means scan everything.
    assert imap_service._search_criteria([], []) == ["ALL"]

    # Multiple senders fold into a nested OR tree.
    assert imap_service._search_criteria(["a@x.com", "b@y.com"], []) == [
        "OR", "FROM", '"b@y.com"', "FROM", '"a@x.com"',
    ]

    # Sender and subject filters are OR-ed so either one retrieves a message.
    assert imap_service._search_criteria(["a@x.com"], ["statement", "invoice"]) == [
        "OR", "FROM", '"a@x.com"',
        "OR", "SUBJECT", '"invoice"', "SUBJECT", '"statement"',
    ]


def test_imap_endpoint_infers_secure_defaults_for_custom_host():
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    profile = EmailSourceProfile(
        source_id="custom-mailbox",
        display_name="Custom Mailbox",
        provider="custom_imap",
        email_address="custom@example.com",
        connection_settings={"imap_host": " imap.example.com "},
    )

    assert imap_service._imap_endpoint(profile) == ("imap.example.com", 993, True)


def test_imap_endpoint_uses_host_port_when_provided():
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    plain_profile = EmailSourceProfile(
        source_id="plain-mailbox",
        display_name="Plain Mailbox",
        provider="custom_imap",
        email_address="plain@example.com",
        connection_settings={"imap_host": "imap.example.com:143"},
    )
    secure_profile = EmailSourceProfile(
        source_id="secure-mailbox",
        display_name="Secure Mailbox",
        provider="custom_imap",
        email_address="secure@example.com",
        connection_settings={"imap_host": "imap.example.com:993"},
    )

    assert imap_service._imap_endpoint(plain_profile) == ("imap.example.com", 143, False)
    assert imap_service._imap_endpoint(secure_profile) == ("imap.example.com", 993, True)


def test_imap_connect_refuses_plaintext_credentials():
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    profile = EmailSourceProfile(
        source_id="plain-mailbox",
        display_name="Plain Mailbox",
        provider="custom_imap",
        email_address="plain@example.com",
        connection_settings={"imap_host": "imap.example.com:143"},
    )

    with pytest.raises(imap_service.ImapProviderError, match="must use TLS"):
        imap_service._connect(profile)


def test_imap_endpoint_uses_known_provider_host():
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    profile = EmailSourceProfile(
        source_id="yahoo-mailbox",
        display_name="Yahoo Mailbox",
        provider="yahoo_imap",
        email_address="yahoo@example.com",
    )

    assert imap_service._imap_endpoint(profile) == ("imap.mail.yahoo.com", 993, True)


def test_imap_connection_reports_case_sensitive_folder_guidance(monkeypatch):
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    class FakeMailbox:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, _email_address, _password):
            return None

        def select(self, folder, readonly=True):
            assert folder == "inbox"
            assert readonly is True
            return "NO", [b"Mailbox does not exist"]

    profile = EmailSourceProfile(
        source_id="folder-case",
        display_name="Folder Case",
        provider="custom_imap",
        email_address="folder@example.com",
        folder="inbox",
        connection_settings={"imap_host": "imap.example.com"},
    )

    monkeypatch.setattr(imap_service, "_connect", lambda _profile: FakeMailbox())

    with pytest.raises(imap_service.ImapProviderError) as exc:
        imap_service.test_connection(profile, "app-password")

    message = str(exc.value)
    assert 'IMAP folder "inbox" could not be opened' in message
    assert "case-sensitive" in message
    assert "Email Ingestion profile folder value" in message


def test_imap_attachment_extraction_ignores_non_pdf_parts():
    from app.services import imap_service

    message = EmailMessage()
    message["Subject"] = "Statement"
    message.set_content("Attached statement")
    message.add_attachment(b"%PDF-1.4\nstatement\n%%EOF", maintype="application", subtype="octet-stream", filename="statement.pdf")
    message.add_attachment(b"fake image", maintype="image", subtype="jpeg", filename="footer.jpg")
    message.add_attachment(b"fake image", maintype="image", subtype="jpeg", filename="header.jpg")

    attachments = list(imap_service._attachments(message))

    assert len(attachments) == 1
    assert attachments[0].filename == "statement.pdf"
    assert attachments[0].content_type == "application/octet-stream"


def test_imap_message_size_guard_skips_oversized_fetch(monkeypatch):
    from app.services import imap_service

    class FakeMailbox:
        def uid(self, command, message_id, query):
            assert command == "fetch"
            assert message_id == b"1"
            assert query == "(RFC822.SIZE)"
            return "OK", [b"1 (RFC822.SIZE 99999999)"]

    monkeypatch.setattr(imap_service.settings, "max_attachment_size_bytes", 1024)

    assert imap_service._message_exceeds_fetch_limit(FakeMailbox(), b"1") is True


def test_sender_or_subject_filters_keep_sender_only_match(client, email_payload):
    # OR semantics: a message from an allowed sender is retrieved even when its
    # subject does not match the subject keywords (the BPI vs HSBC case).
    client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "mailbox-primary",
            "display_name": "Credit Cards",
            "provider": "custom_imap",
            "email_address": "finance@example.com",
            "folder": "Inbox",
            "sender_allowlist": ["mail.hsbc.com.ph", "bpi.com.ph"],
            "subject_contains": ["e-Statement"],
        },
    )
    pdf = b"%PDF-1.4\nstatement\n%%EOF"
    b64 = base64.b64encode(pdf).decode("ascii")

    def _msg(mid, sender, subject, name):
        return {
            "message_id": mid,
            "sender": sender,
            "subject": subject,
            "received_at": "2026-06-18T08:30:00Z",
            "attachments": [{
                "attachment_id": "att-" + mid,
                "filename": name,
                "content_type": "application/pdf",
                "size_bytes": len(pdf),
                "content_base64": b64,
            }],
        }

    email_payload["messages"][0] = _msg("m-noise", "alerts@example.test", "Unrelated notice", "noise.pdf")
    email_payload["messages"].append(_msg("m-hsbc", "HSBC <creditcardstatement@mail.hsbc.com.ph>", "Your HSBC GOLD VISA e-Statement", "hsbc.pdf"))
    email_payload["messages"].append(_msg("m-bpi", "BPI <bpi_cards_estatement@bpi.com.ph>", "Your BPI Credit Card Electronic Statement of Account", "bpi.pdf"))

    payload = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload).json()

    assert payload["summary"]["message_count"] == 2
    retrieved = {c["source"]["message_id"] for c in payload["candidates"]}
    assert retrieved == {"m-hsbc", "m-bpi"}


def test_imap_login_failure_is_wrapped_as_provider_error(monkeypatch):
    # A wrong app password raises imaplib.IMAP4.error; callers only handle
    # ImapProviderError, so the adapter must wrap it (review finding H1).
    import imaplib

    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    class FakeMailbox:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, _email_address, _password):
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")

    profile = EmailSourceProfile(
        source_id="wrong-password",
        display_name="Wrong Password",
        provider="custom_imap",
        email_address="user@example.com",
        connection_settings={"imap_host": "imap.example.com"},
    )
    monkeypatch.setattr(imap_service, "_connect", lambda _profile: FakeMailbox())

    with pytest.raises(imap_service.ImapProviderError, match="IMAP connection test failed"):
        imap_service.test_connection(profile, "bad-password")


def test_imap_date_criteria_use_rfc3501_dates():
    # The retrieval window becomes SINCE/BEFORE with locale-independent month
    # names (review finding H4).
    from datetime import UTC, datetime

    from app.services import imap_service

    criteria = imap_service._date_criteria(
        datetime(2026, 7, 1, 15, 30, tzinfo=UTC),
        datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert criteria == ["SINCE", "01-Jul-2026", "BEFORE", "02-Jul-2026"]


def test_cross_run_dedup_survives_changing_imap_sequence_ids(
    run_ingestion_func, ingestion_request_cls, email_payload, monkeypatch
):
    # Sequence-style message ids change between mailbox sessions, so cross-run
    # dedup must key on the stable Message-ID header + content hash (finding H3).
    from app.services import ingestion_service

    class Queued:
        is_success = True
        status_code = 200

        @staticmethod
        def json():
            return {"ingestion_id": "ing_dedup_1", "status": "queued", "handoff": {"content_reference": "blob://x"}}

    monkeypatch.setattr(ingestion_service.httpx, "post", lambda *_a, **_k: Queued())

    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False
    email_payload["messages"][0]["message_id"] = "42"
    first = run_ingestion_func(ingestion_request_cls(**email_payload))
    assert first.summary.handed_off_count == 1

    message = email_payload["messages"][0]
    dedup_key = f"{email_payload['source_id']}:{message['internet_message_id']}:{first.candidates[0].sha256}"
    run_ingestion_func.__globals__["run_history_service"].mark_ingestion_processed(
        first.candidates[0].handoff.ingestion_id,
        "doc-1",
        first.run_id,
        dedup_key,
    )

    email_payload["messages"][0]["message_id"] = "99"  # same email, new session id
    email_payload["policy"]["dry_run"] = True
    email_payload["policy"]["handoff_to_file_ingestion"] = False
    second = run_ingestion_func(ingestion_request_cls(**email_payload))

    assert second.summary.duplicate_count == 1
    assert second.candidates[0].status.value == "duplicate"
    assert second.candidates[0].findings[0].code == "DUPLICATE_EMAIL_ATTACHMENT_PREVIOUSLY_IMPORTED"


def test_create_source_returns_conflict_for_existing_id(client):
    # POST must not silently overwrite an existing profile (review finding M4).
    body = {
        "source_id": "dup-source",
        "display_name": "Dup Source",
        "provider": "custom_imap",
        "email_address": "dup@example.com",
    }

    assert client.post("/api/v1/email-ingestion-sources", json=body).status_code == 200
    response = client.post("/api/v1/email-ingestion-sources", json=body)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_oversized_message_skip_is_reported_to_caller(monkeypatch):
    # A message dropped by the pre-fetch size guard must be reported so the run
    # can surface a finding instead of silently losing a small PDF inside a
    # large MIME email (external review P2).
    from app.models.ingestion import EmailSourceProfile
    from app.services import imap_service

    class FakeMailbox:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, _email, _password):
            return None

        def select(self, _folder, readonly=True):
            return "OK", [b"1"]

        def uid(self, command, *args):
            if command == "search":
                return "OK", [b"7"]
            assert command == "fetch"
            assert args[1] == "(RFC822.SIZE)"
            return "OK", [b"7 (RFC822.SIZE 99999999)"]

    profile = EmailSourceProfile(
        source_id="oversized",
        display_name="Oversized",
        provider="custom_imap",
        email_address="big@example.com",
        connection_settings={"imap_host": "imap.example.com"},
    )
    monkeypatch.setattr(imap_service, "_connect", lambda _profile: FakeMailbox())
    monkeypatch.setattr(imap_service.settings, "max_attachment_size_bytes", 1024)

    skipped: list[dict] = []
    messages = imap_service.fetch_messages(profile, "pw", 10, skipped_messages=skipped)

    assert messages == []
    assert len(skipped) == 1
    assert skipped[0]["message_id"] == "7"
    assert skipped[0]["size_bytes"] == 99999999
    assert skipped[0]["limit_bytes"] > 1024


def test_delete_profile_keeps_secret_shared_by_another_profile():
    # Two profiles may reference the same secret_ref (the field is editable), so
    # deleting one profile must not delete the shared mailbox secret; deleting
    # the last referencing profile removes it (external review pass 3, P1).
    from app.models.ingestion import EmailSourceProfileCreate
    from app.services.secret_service import resolve_secret
    from app.services.source_profile_service import create_source_profile, delete_source_profile

    def _profile(source_id):
        return EmailSourceProfileCreate(
            source_id=source_id,
            display_name=source_id,
            provider="custom_imap",
            email_address=f"{source_id}@example.test",
            app_password="shared-password",
            secret_ref="stats-email-shared-secret",
            connection_settings={"imap_host": "imap.example.test"},
        )

    create_source_profile(_profile("shared-a"))
    create_source_profile(_profile("shared-b"))
    assert resolve_secret("stats-email-shared-secret") == "shared-password"

    assert delete_source_profile("shared-a") is True
    assert resolve_secret("stats-email-shared-secret") == "shared-password"  # still referenced by shared-b

    assert delete_source_profile("shared-b") is True
    assert resolve_secret("stats-email-shared-secret") is None  # last reference gone


def test_polling_schedule_rejects_invalid_time_of_day(client):
    response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "bad-schedule",
            "display_name": "Bad Schedule",
            "provider": "custom_imap",
            "email_address": "bad@example.com",
            "polling_schedule": {"cadence": "daily", "time_of_day": "25:99"},
        },
    )

    assert response.status_code == 422
