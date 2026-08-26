from datetime import datetime, time


def is_quiet_hours(
    now: datetime,
    *,
    start_hour: int = 22,
    end_hour: int = 7,
    enabled: bool = True,
) -> bool:
    """Return True when household notifications should be deferred."""
    if not enabled:
        return False
    current = now.time()
    start = time(hour=start_hour)
    end = time(hour=end_hour)
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start <= current < end
    return current >= start or current < end


def should_defer_reminder(
    now: datetime,
    *,
    start_hour: int = 22,
    end_hour: int = 7,
    enabled: bool = True,
) -> bool:
    """Defer due-date, recurring, and one-shot reminder pushes during quiet hours."""
    return is_quiet_hours(
        now,
        start_hour=start_hour,
        end_hour=end_hour,
        enabled=enabled,
    )
