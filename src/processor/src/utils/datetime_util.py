from __future__ import annotations

from datetime import datetime, timezone


def get_current_timestamp_utc(now: datetime | None = None) -> str:
    """Return a human-readable UTC timestamp for report footers.

    Format is: "January 7, 2026 10:30 UTC".
    """

    dt = now or datetime.now(timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return f"{dt.strftime('%B')} {dt.day}, {dt.strftime('%Y %H:%M')} UTC"
