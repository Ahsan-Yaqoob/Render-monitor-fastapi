from datetime import datetime


def get_current_timestamp():
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def parse_timestamp(timestamp_str):
    """Parse ISO timestamp string to datetime object."""
    try:
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return None


def calculate_duration(start_time, end_time):
    """Calculate duration between two timestamps in minutes."""
    try:
        if isinstance(start_time, str):
            start_time = parse_timestamp(start_time)
        if isinstance(end_time, str):
            end_time = parse_timestamp(end_time)
        
        if start_time and end_time:
            delta = end_time - start_time
            return delta.total_seconds() / 60
        return 0
    except Exception:
        return 0


def format_duration_readable(minutes):
    """Format duration in minutes to readable format (e.g., '2h 30m')."""
    if minutes < 1:
        return "< 1 min"
    
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    if hours == 0:
        return f"{mins}m"
    elif mins == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {mins}m"


def time_ago(timestamp_str):
    """Get human-readable time difference (e.g., '2 hours ago')."""
    try:
        if isinstance(timestamp_str, str):
            dt = parse_timestamp(timestamp_str)
        else:
            dt = timestamp_str
        
        if not dt:
            return "Unknown"
        
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"
    except Exception:
        return "Unknown"
