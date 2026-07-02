"""M12 - Email Ingestion Module Start
Covers run-history persistence, cross-run deduplication, handoff-failure
recording, and safe mapping of saved-secret decrypt failures.
M12 End"""

def _handoff_payload(email_payload):
    email_payload["policy"]["handoff_to_file_ingestion"] = True
    email_payload["policy"]["dry_run"] = False
    return email_payload


class _QueuedResponse:
    is_success = True
    status_code = 200

    @staticmethod
    def json():
        return {
            "ingestion_id": "ingest_email_001",
            "status": "queued",
            "handoff": {"content_reference": "storage://email/statement.pdf"},
        }


class _RejectedResponse:
    is_success = False
    status_code = 503

    @staticmethod
    def json():
        return {"status": "error", "detail": "file intake unavailable"}


def test_run_history_persists_and_is_listable(client, email_payload):
    run_response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    list_response = client.get("/api/v1/email-ingestions/runs", params={"source_id": "mailbox-primary"})
    assert list_response.status_code == 200
    runs = list_response.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id
    assert runs[0]["mode"] == "dry_run"
    assert runs[0]["summary"]["attachment_count"] == 1
    assert runs[0]["correlation_id"]

    detail_response = client.get(f"/api/v1/email-ingestions/runs/{run_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run_id"] == run_id
    assert len(detail["candidates"]) == 1
    assert detail["candidates"][0]["dedup_key"]
    assert detail["candidates"][0]["status"] == "retrieved"


def test_unknown_run_detail_returns_404(client):
    response = client.get("/api/v1/email-ingestions/runs/email_run_missing")
    assert response.status_code == 404


def test_delete_source_profile_removes_it(client):
    created = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "temp-mailbox",
            "display_name": "Temp Mailbox",
            "provider": "custom_imap",
            "email_address": "temp@example.test",
            "folder": "Inbox",
        },
    )
    assert created.status_code == 200

    deleted = client.delete("/api/v1/email-ingestion-sources/temp-mailbox")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    listing = client.get("/api/v1/email-ingestion-sources").json()
    assert all(source["source_id"] != "temp-mailbox" for source in listing["sources"])

    # Deleting again is a 404.
    assert client.delete("/api/v1/email-ingestion-sources/temp-mailbox").status_code == 404


def test_scheduled_runs_rejects_admin_bearer_without_internal_key(client):
    # The client fixture carries an admin bearer token but no internal key.
    response = client.post("/api/v1/email-ingestions/scheduled-runs")
    assert response.status_code == 403


def test_scheduled_runs_accepts_internal_key(client):
    response = client.post(
        "/api/v1/email-ingestions/scheduled-runs",
        headers={"X-Stats-Internal-Key": "m12-test-internal-api-key"},
    )
    assert response.status_code == 200
    assert response.json()["ran_count"] == 0


def test_persistent_dedup_skips_previously_imported_attachment(
    run_ingestion_func, ingestion_request_cls, email_payload, monkeypatch
):
    _handoff_payload(email_payload)
    calls = {"count": 0}

    def fake_post(*_args, **_kwargs):
        calls["count"] += 1
        return _QueuedResponse()

    monkeypatch.setattr("app.services.ingestion_service.httpx.post", fake_post)

    first = run_ingestion_func(ingestion_request_cls(**email_payload))
    assert first.candidates[0].status == "handed_off"
    assert first.summary.handed_off_count == 1

    second = run_ingestion_func(ingestion_request_cls(**email_payload))
    assert second.candidates[0].status == "duplicate"
    assert second.summary.handed_off_count == 0
    assert second.summary.duplicate_count == 1
    assert any(
        finding.code == "DUPLICATE_EMAIL_ATTACHMENT_PREVIOUSLY_IMPORTED"
        for finding in second.candidates[0].findings
    )
    # The previously imported attachment must not be handed off a second time.
    assert calls["count"] == 1


def test_dry_run_after_import_shows_already_imported(
    run_ingestion_func, ingestion_request_cls, email_payload, monkeypatch
):
    handoff_payload = _handoff_payload(dict(email_payload))
    monkeypatch.setattr("app.services.ingestion_service.httpx.post", lambda *_a, **_k: _QueuedResponse())
    run_ingestion_func(ingestion_request_cls(**handoff_payload))

    dry_payload = dict(email_payload)
    dry_payload["policy"] = {"handoff_to_file_ingestion": False, "dry_run": True, "deduplicate": True}
    dry_result = run_ingestion_func(ingestion_request_cls(**dry_payload))
    assert dry_result.candidates[0].status == "duplicate"


def test_handoff_failure_is_recorded_in_run_history(client, email_payload, monkeypatch):
    _handoff_payload(email_payload)
    monkeypatch.setattr("app.services.ingestion_service.httpx.post", lambda *_a, **_k: _RejectedResponse())

    run_response = client.post("/api/v1/email-ingestions/automated-runs", json=email_payload)
    assert run_response.status_code == 200
    body = run_response.json()
    run_id = body["run_id"]
    assert body["status"] == "failed"
    assert body["candidates"][0]["status"] == "failed"

    detail = client.get(f"/api/v1/email-ingestions/runs/{run_id}").json()
    assert detail["status"] == "failed"
    assert detail["error_message"]
    candidate = detail["candidates"][0]
    assert candidate["status"] == "failed"
    assert "FILE_INGESTION_HANDOFF_FAILED" in candidate["finding_codes"]
    assert candidate["handoff_error"]


def test_saved_secret_decrypt_failure_maps_to_actionable_error(
    run_ingestion_func, ingestion_request_cls, monkeypatch
):
    from app.services.secret_service import SECRET_UNREADABLE_MESSAGE, SecretResolutionError
    from app.services.source_profile_service import create_source_profile
    from app.models.ingestion import EmailSourceProfileCreate

    profile = create_source_profile(
        EmailSourceProfileCreate(
            source_id="locked-secret-mailbox",
            display_name="Locked Secret Mailbox",
            provider="custom_imap",
            email_address="locked@example.test",
            folder="Inbox",
            app_password="initial-password",
            connection_settings={"imap_host": "imap.example.test"},
        )
    )

    monkeypatch.setitem(run_ingestion_func.__globals__, "get_source_profile", lambda _source_id: profile)
    monkeypatch.setitem(run_ingestion_func.__globals__, "supports_imap_provider", lambda _provider: True)
    secret_error_cls = run_ingestion_func.__globals__["SecretResolutionError"]

    def raise_secret_error(_secret_ref):
        raise secret_error_cls(SECRET_UNREADABLE_MESSAGE)

    monkeypatch.setitem(run_ingestion_func.__globals__, "resolve_secret", raise_secret_error)

    request = ingestion_request_cls(
        source_id="locked-secret-mailbox",
        policy={"dry_run": True, "handoff_to_file_ingestion": False},
        messages=[],
    )
    result = run_ingestion_func(request)

    assert result.status == "failed"
    assert result.summary.failed_count == 1
    finding = result.findings[0]
    assert finding.code == "MAILBOX_SECRET_UNREADABLE"
    assert finding.message == SECRET_UNREADABLE_MESSAGE


def test_test_connection_maps_secret_decrypt_failure(client, monkeypatch):
    from app.services.secret_service import SECRET_UNREADABLE_MESSAGE, SecretResolutionError

    create_response = client.post(
        "/api/v1/email-ingestion-sources",
        json={
            "source_id": "locked-test-mailbox",
            "display_name": "Locked Test Mailbox",
            "provider": "custom_imap",
            "email_address": "locked-test@example.test",
            "folder": "Inbox",
            "app_password": "initial-password",
            "connection_settings": {"imap_host": "imap.example.test"},
        },
    )
    assert create_response.status_code == 200

    def raise_secret_error(_secret_ref):
        raise SecretResolutionError(SECRET_UNREADABLE_MESSAGE)

    monkeypatch.setattr("app.routes.sources.resolve_secret", raise_secret_error)

    response = client.post(
        "/api/v1/email-ingestion-sources/locked-test-mailbox/test-connection",
        json={},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["message"] == SECRET_UNREADABLE_MESSAGE
