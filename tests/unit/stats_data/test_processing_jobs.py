"""M9 - Stats Data and Persistence Start
Tests processing-job persistence hardening behavior.
M9 End"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))

from stats_data import processing_jobs  # noqa: E402
from stats_data.processing_jobs import ProcessingJob  # noqa: E402


def test_create_processing_job_closes_cursor_when_insert_fails():
    connection = _FailingConnection()

    with pytest.raises(RuntimeError, match="insert failed"):
        processing_jobs.create_processing_job(
            connection,
            ingestion_id="ingestion_1",
            uploaded_by_user_id="user_1",
            original_filename="receipt.jpg",
        )

    assert connection.cursor_instance.closed is True
    assert connection.committed is False


def test_append_processing_step_closes_cursor_when_insert_fails():
    connection = _FailingConnection()

    with pytest.raises(RuntimeError, match="insert failed"):
        processing_jobs.append_processing_step(
            connection,
            "job_1",
            module_name="M5",
            step_name="document_parsing",
            status="completed",
            started_at_utc="2026-06-07T01:02:03Z",
        )

    assert connection.cursor_instance.closed is True
    assert connection.committed is False


def test_terminal_processing_job_is_not_overwritten(monkeypatch):
    completed = ProcessingJob(
        job_id="job_1",
        ingestion_id="ingestion_1",
        uploaded_by_user_id="user_1",
        original_filename="receipt.jpg",
        source_type="manual_upload",
        source_id="stats-web-upload",
        sha256="abc123",
        status="completed",
        stage="completed",
        message="Transactions checked.",
    )
    connection = _TrackingConnection()
    monkeypatch.setattr(processing_jobs, "get_processing_job", lambda *_args: completed)

    result = processing_jobs.update_processing_job(
        connection,
        "job_1",
        status="running",
        stage="parsing",
        message="This late update should be ignored.",
    )

    assert result is completed
    assert connection.cursor_instance is None
    assert connection.committed is False


class _FailingConnection:
    def __init__(self):
        self.cursor_instance = _FailingCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


class _FailingCursor:
    def __init__(self):
        self.closed = False

    def execute(self, *_args):
        raise RuntimeError("insert failed")

    def close(self):
        self.closed = True


class _TrackingConnection:
    def __init__(self):
        self.cursor_instance = None
        self.committed = False

    def cursor(self):
        self.cursor_instance = object()
        return self.cursor_instance

    def commit(self):
        self.committed = True
