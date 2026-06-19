from datetime import datetime, timezone


def get_current_timestamp():
    """Current time as UTC-aware ISO string (e.g. 2026-06-19T10:00:00+00:00)."""
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(timestamp_str):
    try:
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return None


def calculate_duration(start_time, end_time):
    """Duration between two timestamps in minutes. Handles mixed naive/aware datetimes."""
    try:
        if isinstance(start_time, str):
            start_time = parse_timestamp(start_time)
        if isinstance(end_time, str):
            end_time = parse_timestamp(end_time)
        if not (start_time and end_time):
            return 0
        # Normalize both to the same timezone awareness
        if start_time.tzinfo is not None and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        elif start_time.tzinfo is None and end_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        return max(0, (end_time - start_time).total_seconds() / 60)
    except Exception:
        return 0


def format_duration_readable(minutes):
    if minutes < 1:
        return "< 1 min"
    hours = int(minutes // 60)
    mins  = int(minutes % 60)
    if hours == 0:    return f"{mins}m"
    if mins  == 0:    return f"{hours}h"
    return f"{hours}h {mins}m"


def time_ago(timestamp_str):
    """Human-readable time since timestamp. Handles both naive and UTC-aware strings."""
    try:
        dt = parse_timestamp(timestamp_str) if isinstance(timestamp_str, str) else timestamp_str
        if not dt:
            return "Unknown"
        now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()
        seconds = max(0, (now - dt).total_seconds())
        if seconds < 60:    return f"{int(seconds)}s ago"
        if seconds < 3600:  return f"{int(seconds / 60)}m ago"
        if seconds < 86400: return f"{int(seconds / 3600)}h ago"
        return f"{int(seconds / 86400)}d ago"
    except Exception:
        return "Unknown"
