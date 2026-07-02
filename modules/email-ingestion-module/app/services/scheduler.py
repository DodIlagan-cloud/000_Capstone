"""M12 - Email Ingestion Module Start
Automatic ingestion scheduler.

A single cloud tick (Azure Container Apps Job cron) calls run_due_profiles. The job
ticks at least as often as the finest cadence (hourly); this service decides which
profiles are due and runs each end-to-end: import (mailbox -> intake) then ingest
(intake -> database). Default cadence is off, so nothing runs automatically unless a
profile is explicitly scheduled on the Email Setup page.
M12 End"""

import logging
from threading import Lock
from datetime import UTC, datetime
from typing import Optional

from app.models.ingestion import AutomatedEmailIngestionRequest, IntakePolicy
from app.services import run_history_service
from app.services.ingestion_service import run_automated_email_ingestion
from app.services.pipeline_runner import process_imported_run
from app.services.schedule_rules import is_schedule_due
from app.services.source_profile_service import list_source_profiles, mark_auto_run


logger = logging.getLogger(__name__)

# NOTE: this lock is per-process only. It stops overlapping ticks within one
# uvicorn worker, but NOT across multiple workers or job replicas. The scheduled
# trigger (Azure Container Apps Job) must run with parallelism/replica count 1;
# use a distributed lock (e.g. sp_getapplock) before scaling it out.
_scheduler_lock = Lock()


def run_due_profiles_with_lock(now: Optional[datetime] = None) -> dict:
    """Run due profiles unless another scheduled tick is already active."""
    if not _scheduler_lock.acquire(blocking=False):
        logger.warning("M12 scheduled auto-run skipped because another tick is already running.")
        return {
            "ran_count": 0,
            "locked": True,
            "results": [],
            "note": "scheduled_tick_already_running",
        }
    try:
        result = run_due_profiles(now=now)
        result["locked"] = False
        return result
    finally:
        _scheduler_lock.release()


def run_due_profiles(
    now: Optional[datetime] = None,
    *,
    clients=None,
    list_profiles=None,
    import_runner=None,
    ingest_runner=None,
    mark=None,
    pending_runs=None,
) -> dict:
    """Run every enabled, due profile end-to-end. Collaborators are injectable for tests."""
    now = now or datetime.now(UTC)
    list_profiles = list_profiles or (lambda: list_source_profiles().sources)
    import_runner = import_runner or _default_import_runner
    ingest_runner = ingest_runner or process_imported_run
    mark = mark or mark_auto_run
    pending_runs = pending_runs or run_history_service.list_unprocessed_import_run_ids

    results = []
    for profile in list_profiles():
        if not getattr(profile, "enabled", False):
            continue
        schedule = getattr(profile, "polling_schedule", None)
        cadence = getattr(schedule, "cadence", "off") if schedule else "off"
        time_of_day = getattr(schedule, "time_of_day", None) if schedule else None
        if not is_schedule_due(cadence, time_of_day, getattr(profile, "last_auto_run_at", None), now):
            continue

        import_result = import_runner(profile.source_id)
        import_status = _status_value(import_result)
        import_run_id = getattr(import_result, "run_id", None)

        # Only ingest the run this tick just produced. A failed import (or one without
        # a run id) must NOT fall back to processing an older successful run, and must
        # NOT advance the schedule - leave the profile due so the next tick retries.
        if import_status == "failed" or not import_run_id:
            results.append(
                {
                    "source_id": profile.source_id,
                    "import_status": import_status,
                    "ingest_status": None,
                    "note": "import_failed_or_no_run_id; ingest skipped, schedule not advanced",
                }
            )
            logger.warning(
                "M12 scheduled auto-run skipped ingest. source_id=%s import=%s run_id=%s",
                profile.source_id, import_status, import_run_id,
            )
            continue

        ingest_result = ingest_runner(profile.source_id, run_id=import_run_id, clients=clients)
        # Retry earlier import runs whose handed-off files never reached the
        # database (e.g. a downstream module was down on a previous tick). The
        # files are already in intake, so mailbox dedup would otherwise skip them
        # forever. Retries are bounded per tick and the processed-marker
        # idempotency prevents double saves once a run finally succeeds.
        retried = _retry_unprocessed_runs(profile.source_id, import_run_id, pending_runs, ingest_runner, clients)
        # The schedule advances even when the ingest step fails: the retry above
        # (next tick) and the manual "Ingest to database" button cover recovery,
        # while re-importing from the mailbox every tick would gain nothing.
        mark(profile.source_id, now.isoformat())
        results.append(
            {
                "source_id": profile.source_id,
                "import_status": import_status,
                "ingest_status": _status_value(ingest_result),
                "saved_record_count": getattr(ingest_result, "saved_record_count", 0),
                "review_item_count": getattr(ingest_result, "review_item_count", 0),
                "retried_runs": retried,
            }
        )
        logger.info(
            "M12 scheduled auto-run completed. source_id=%s import=%s ingest=%s retried=%s",
            profile.source_id, results[-1]["import_status"], results[-1]["ingest_status"], len(retried),
        )

    return {"ran_count": len(results), "results": results}


def _retry_unprocessed_runs(source_id: str, current_run_id: str, pending_runs, ingest_runner, clients) -> list[dict]:
    try:
        pending = pending_runs(source_id)
    except Exception as exc:  # pragma: no cover - lookup guard
        logger.warning("M12 scheduled retry lookup failed. source_id=%s error=%s", source_id, str(exc))
        return []
    retried: list[dict] = []
    # Oldest first so backlogged runs drain in order; skip the run this tick just
    # ingested.
    for run_id in reversed([rid for rid in pending if rid and rid != current_run_id]):
        outcome = ingest_runner(source_id, run_id=run_id, clients=clients)
        retried.append({"run_id": run_id, "ingest_status": _status_value(outcome)})
        logger.info(
            "M12 scheduled retry of unprocessed import run. source_id=%s run_id=%s ingest=%s",
            source_id, run_id, retried[-1]["ingest_status"],
        )
    return retried


def _default_import_runner(source_id: str):
    # A real (non-dry) import that hands accepted attachments to intake.
    request = AutomatedEmailIngestionRequest(
        source_id=source_id,
        mode="handoff",
        policy=IntakePolicy(
            dry_run=False,
            handoff_to_file_ingestion=True,
            deduplicate=True,
            detect_password_protected_pdfs=True,
        ),
    )
    return run_automated_email_ingestion(request)


def _status_value(result) -> Optional[str]:
    status = getattr(result, "status", None)
    return status.value if hasattr(status, "value") else status
