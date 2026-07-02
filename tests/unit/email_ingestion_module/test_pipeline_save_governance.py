"""M12 - Email Ingestion Module Start
Governance contract for the automated database save (C2).

The automated pipeline must flow the UNREVIEWED path: it must not claim upload-review
human confirmation. That is what makes M9 govern the save - route unknown /
low-confidence / out-of-vocabulary rows to pending recognition suggestions +
review_items instead of activating labels or marking classifications confirmed
(M9 spec: Recognition Label Suggestions And Synchronization; the M9
_classification_confirmation_allowed gate requires classification_human_confirmed +
classification_source=user_confirmed_* + classification_confirmation_mode=
upload_transaction_review). This test locks that M12-side invariant.
M12 End"""


class _FakeResponse:
    def raise_for_status(self):
        return None

    @staticmethod
    def json():
        return {"document_id": "doc-1", "saved_record_count": 1, "review_item_count": 1}


class _CapturingHttp:
    def __init__(self):
        self.captured = {}

    def post(self, url, headers=None, json=None, **_kwargs):
        self.captured = {"url": url, "headers": headers, "json": json}
        return _FakeResponse()


def _settings():
    from app.pipeline.config import OrchestratorSettings

    return OrchestratorSettings(
        stats_data_base_url="http://stats-data",
        document_parsing_base_url="http://parse",
        transaction_extraction_base_url="http://extract",
        data_validation_base_url="http://validate",
        file_intake_base_url="http://intake",
        internal_api_key="internal-key",
        automated_uploaded_by_user_id="system-email-ingestion",
        automated_saved_by_user_id="system-email-automation",
        allow_ocr_fallback="true",
        classification_threshold="0.1",
        request_timeout_seconds=5.0,
    )


def test_automated_save_is_unreviewed_and_uses_system_identity():
    from app.pipeline.clients import PipelineClients
    from app.pipeline.models import PipelineRunRequest

    http = _CapturingHttp()
    clients = PipelineClients(_settings(), http=http)
    request = PipelineRunRequest(ingestion_id="ing-1", original_filename="statement.pdf")
    validation_result = {
        "summary": {"valid_record_count": 1, "review_item_count": 1},
        "transaction_candidates": [{"classification_source": "ai_suggestion"}],
    }

    clients.save(validation_result, request, "job-1")

    body = http.captured["json"]
    # System provenance, not a real user.
    assert body["saved_by_user_id"] == "system-email-automation"
    assert body["uploaded_by_user_id"] == "system-email-ingestion"
    assert body["processing_job_id"] == "job-1"
    # The M8 validation result is passed through unchanged.
    assert body["validation_result"] == validation_result
    # It must NOT claim upload-review human confirmation (which would let M9 activate
    # labels / mark classifications confirmed without review).
    assert "classification_human_confirmed" not in body
    assert "classification_confirmation_mode" not in body
    assert "classification_confirmed_by_user_id" not in body
    # Internal service key is sent for server-to-server auth.
    assert http.captured["headers"] == {"X-Stats-Internal-Key": "internal-key"}


def test_pipeline_clients_require_internal_service_key():
    from app.pipeline.clients import PipelineClients

    settings = _settings()
    settings.internal_api_key = None

    try:
        PipelineClients(settings, http=_CapturingHttp())
    except RuntimeError as exc:
        assert "STATS_INTERNAL_API_KEY" in str(exc)
    else:
        raise AssertionError("PipelineClients should require STATS_INTERNAL_API_KEY.")
