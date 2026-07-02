"""M12 - Email Ingestion Module Start
Tests that post_process_policy (mark-as-read / move) runs after a successful real
import, and not on dry runs. IMAP + handoff mocked.

Note on the harness: the conftest reloads `app.*` per fixture, so a fixture-imported
callable can bind to a different in-memory store than a test-body import. To avoid
that, this test imports the run function AND create_source_profile in-body (same
post-reload module state) and monkeypatches the `ingestion_service` module object
directly.
M12 End"""


class _Queued:
    is_success = True
    status_code = 200

    @staticmethod
    def json():
        return {"ingestion_id": "ing_pp_1", "status": "queued", "handoff": {"content_reference": "blob://pp"}}


def _run(monkeypatch, *, mark_as_read, dry_run):
    from app.models.ingestion import (
        AutomatedEmailIngestionRequest,
        EmailAttachmentInput,
        EmailMessageInput,
        EmailSourceProfileCreate,
    )
    from app.services import ingestion_service
    from app.services.source_profile_service import create_source_profile
    import base64

    create_source_profile(
        EmailSourceProfileCreate(
            source_id="pp-mailbox",
            display_name="Post Process Mailbox",
            provider="custom_imap",
            email_address="pp@example.test",
            folder="Inbox",
            app_password="pw",
            connection_settings={"imap_host": "imap.example.test"},
            post_process_policy={"mark_as_read": mark_as_read},
        )
    )

    pdf = base64.b64encode(b"%PDF-1.4 post-process %%EOF").decode("ascii")
    message = EmailMessageInput(
        message_id="1",
        internet_message_id="<m1@example.test>",
        sender="statements@example.test",
        subject="statement",
        received_at="2026-07-01T00:00:00Z",
        attachments=[
            EmailAttachmentInput(
                attachment_id="1",
                filename="statement.pdf",
                content_type="application/pdf",
                size_bytes=25,
                content_base64=pdf,
            )
        ],
    )

    captured = {"calls": 0}

    def fake_post_process(profile, internet_message_ids, password):
        captured["calls"] += 1
        captured["ids"] = set(internet_message_ids)
        captured["password"] = password

    monkeypatch.setattr(ingestion_service, "supports_imap_provider", lambda _p: True)
    monkeypatch.setattr(ingestion_service, "resolve_secret", lambda _ref: "pw")
    monkeypatch.setattr(ingestion_service, "fetch_messages", lambda profile, password, maxm, **_kw: [message])
    monkeypatch.setattr(ingestion_service.httpx, "post", lambda *_a, **_k: _Queued())
    monkeypatch.setattr(ingestion_service, "apply_post_process", fake_post_process)

    request = AutomatedEmailIngestionRequest(
        source_id="pp-mailbox",
        policy={
            "dry_run": dry_run,
            "handoff_to_file_ingestion": not dry_run,
            "deduplicate": True,
        },
        messages=[],
    )
    result = ingestion_service.run_automated_email_ingestion(request)
    return result, captured


def test_post_process_runs_after_successful_handoff(clear_email_sources, monkeypatch):
    result, captured = _run(monkeypatch, mark_as_read=True, dry_run=False)

    assert result.summary.handed_off_count == 1
    assert captured["calls"] == 1
    assert captured["ids"] == {"<m1@example.test>"}
    assert captured["password"] == "pw"


def test_post_process_skipped_on_dry_run(clear_email_sources, monkeypatch):
    _result, captured = _run(monkeypatch, mark_as_read=True, dry_run=True)

    assert captured["calls"] == 0
