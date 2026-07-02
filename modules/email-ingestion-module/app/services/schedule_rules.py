"""M12 - Email Ingestion Module Start
Pure polling-cadence due-time rules.

No app/third-party imports, so the scheduling decision is testable in isolation.
All times are UTC.
M12 End"""

from datetime import UTC, datetime, timedelta
from typing import Optional


def is_schedule_due(cadence, time_of_day: Optional[str], last_auto_run_at_iso: Optional[str], now: datetime) -> bool:
    """Decide whether a profile is due. cadence may be a PollingCadence enum or string."""
    cadence_value = cadence.value if hasattr(cadence, "value") else str(cadence or "off")
    if cadence_value == "off":
        return False

    last = parse_iso(last_auto_run_at_iso)
    if cadence_value == "hourly":
        return last is None or (now - last) >= timedelta(hours=1)
    if cadence_value == "daily":
        hour, minute = parse_time_of_day(time_of_day)
        scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now < scheduled_today:
            return False
        return last is None or last < scheduled_today
    return False


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_time_of_day(time_of_day: Optional[str]) -> tuple[int, int]:
    if not time_of_day:
        return 0, 0
    try:
        hour_text, minute_text = time_of_day.split(":", 1)
        hour = max(0, min(23, int(hour_text)))
        minute = max(0, min(59, int(minute_text)))
        return hour, minute
    except (ValueError, AttributeError):
        return 0, 0
