"""M12 - Email Ingestion Module Start
Tests for automatic-ingestion scheduling: pure due-time rules and run_due_profiles.
M12 End"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.services.schedule_rules import is_schedule_due
from app.services import scheduler
from app.services.scheduler import run_due_profiles, run_due_profiles_with_lock


NOW = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)


def test_off_is_never_due():
    assert is_schedule_due("off", None, None, NOW) is False
    assert is_schedule_due("off", "08:00", None, NOW) is False


def test_hourly_due_rules():
    assert is_schedule_due("hourly", None, None, NOW) is True  # never run
    recent = (NOW - timedelta(minutes=30)).isoformat()
    assert is_schedule_due("hourly", None, recent, NOW) is False
    stale = (NOW - timedelta(hours=2)).isoformat()
    assert is_schedule_due("hourly", None, stale, NOW) is True


def test_daily_due_rules():
    # Before the scheduled time today -> not due.
    assert is_schedule_due("daily", "10:00", None, NOW) is False
    # After scheduled time, never run -> due.
    assert is_schedule_due("daily", "08:00", None, NOW) is True
    # Already ran after today's scheduled time -> not due.
    ran_today = NOW.replace(hour=8, minute=30).isoformat()
    assert is_schedule_due("daily", "08:00", ran_today, NOW) is False
    # Last ran yesterday -> due again today.
    ran_yesterday = (NOW - timedelta(days=1)).isoformat()
    assert is_schedule_due("daily", "08:00", ran_yesterday, NOW) is True


@dataclass
class _Schedule:
    cadence: str
    time_of_day: Optional[str] = None


@dataclass
class _Profile:
    source_id: str
    enabled: bool = True
    last_auto_run_at: Optional[str] = None
    polling_schedule: _Schedule = field(default_factory=lambda: _Schedule("off"))


class _IngestResult:
    def __init__(self):
        self.status = "completed"
        self.saved_record_count = 2
        self.review_item_count = 1


class _ImportResult:
    def __init__(self, run_id="email_run_due"):
        self.run_id = run_id
        self.status = "completed"


def test_run_due_profiles_runs_only_due_enabled_profiles():
    profiles = [
        _Profile("due-hourly", polling_schedule=_Schedule("hourly")),
        _Profile("off-profile", polling_schedule=_Schedule("off")),
        _Profile("disabled", enabled=False, polling_schedule=_Schedule("hourly")),
        _Profile("ran-recently", last_auto_run_at=(NOW - timedelta(minutes=5)).isoformat(), polling_schedule=_Schedule("hourly")),
    ]
    imported = []
    ingested = []
    marked = []

    def ingest_runner(source_id, run_id=None, clients=None):
        ingested.append((source_id, run_id))
        return _IngestResult()

    summary = run_due_profiles(
        now=NOW,
        list_profiles=lambda: profiles,
        import_runner=lambda source_id: imported.append(source_id) or _ImportResult("email_run_due_hourly"),
        ingest_runner=ingest_runner,
        mark=lambda source_id, ts: marked.append(source_id),
    )

    assert summary["ran_count"] == 1
    assert imported == ["due-hourly"]
    assert ingested == [("due-hourly", "email_run_due_hourly")]
    assert marked == ["due-hourly"]
    assert summary["results"][0]["ingest_status"] == "completed"
    assert summary["results"][0]["saved_record_count"] == 2


class _FailedImport:
    run_id = "email_run_failed"
    status = "failed"


def test_run_due_profiles_skips_ingest_and_does_not_advance_on_failed_import():
    profiles = [_Profile("due-hourly", polling_schedule=_Schedule("hourly"))]
    ingested = []
    marked = []

    summary = run_due_profiles(
        now=NOW,
        list_profiles=lambda: profiles,
        import_runner=lambda source_id: _FailedImport(),
        ingest_runner=lambda source_id, run_id=None, clients=None: ingested.append((source_id, run_id)) or _IngestResult(),
        mark=lambda source_id, ts: marked.append(source_id),
    )

    # A failed import must not process an older run and must not advance the schedule.
    assert ingested == []
    assert marked == []
    assert summary["results"][0]["ingest_status"] is None


def test_run_due_profiles_retries_unprocessed_earlier_runs():
    # An ingest that failed on a previous tick left handed-off files unprocessed;
    # the next tick must retry those runs (oldest first) after the new import.
    profiles = [_Profile("due-hourly", polling_schedule=_Schedule("hourly"))]
    ingested = []

    def ingest_runner(source_id, run_id=None, clients=None):
        ingested.append((source_id, run_id))
        return _IngestResult()

    summary = run_due_profiles(
        now=NOW,
        list_profiles=lambda: profiles,
        import_runner=lambda source_id: _ImportResult("email_run_new"),
        ingest_runner=ingest_runner,
        mark=lambda source_id, ts: None,
        pending_runs=lambda source_id: ["email_run_new", "email_run_stuck_2", "email_run_stuck_1"],
    )

    # New run first, then backlog oldest-first; the new run is not retried.
    assert ingested == [
        ("due-hourly", "email_run_new"),
        ("due-hourly", "email_run_stuck_1"),
        ("due-hourly", "email_run_stuck_2"),
    ]
    assert summary["results"][0]["retried_runs"] == [
        {"run_id": "email_run_stuck_1", "ingest_status": "completed"},
        {"run_id": "email_run_stuck_2", "ingest_status": "completed"},
    ]


def test_run_due_profiles_with_lock_skips_overlapping_tick():
    acquired = scheduler._scheduler_lock.acquire(blocking=False)
    assert acquired is True
    try:
        summary = run_due_profiles_with_lock(now=NOW)
    finally:
        scheduler._scheduler_lock.release()

    assert summary["locked"] is True
    assert summary["ran_count"] == 0
    assert summary["note"] == "scheduled_tick_already_running"
