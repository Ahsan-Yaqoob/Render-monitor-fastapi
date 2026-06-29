from fastapi import APIRouter, Query
from backend.services.monitor_service import get_monitor_service
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.utils.helpers import format_duration_readable, time_ago
from datetime import datetime, timedelta
import requests as _requests
import time as _time

# Server-side cache so we don't hammer the AI backend on every frontend refresh
_svc_health_cache: dict = {}
_svc_health_ts: float = 0.0
_SVC_HEALTH_TTL = 300  # 5 minutes

router = APIRouter(prefix="/api", tags=["dashboard"])

monitor_service = get_monitor_service()


@router.get("/status")
async def get_status():
    try:
        snap = monitor_service.get_current_status()
        return {
            'success': True,
            'data': {
                'is_running':        snap.is_running,
                'status':            'RUNNING' if snap.is_running else 'FAILED',
                'last_check':        snap.last_check_time,
                'last_check_time':   snap.last_check_time,
                'last_check_ago':    time_ago(snap.last_check_time),
                'failure_start':     snap.failure_start_time,
                'last_recovery':     snap.last_recovery_time,
                'downtime_minutes':  snap.current_downtime_minutes,
                'downtime_readable': format_duration_readable(snap.current_downtime_minutes),
                'issue_type':        snap.issue_type,
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {'success': False, 'error': str(e)}


@router.get("/history")
def get_history(limit: int = Query(100, ge=1, le=5000), days: int = Query(0, ge=0, le=365)):
    """Return FAILED/RECOVERED events. Reads from Supabase when configured, else CSV."""
    try:
        effective_days = days if days > 0 else 90
        history = monitor_service.get_history(days=effective_days)

        # Secondary date filter for CSV path (DB already filters by days)
        if days > 0 and not monitor_service.db.is_available():
            cutoff = datetime.now() - timedelta(days=days)
            history = [
                r for r in history
                if datetime.fromisoformat(r['timestamp']) >= cutoff
            ]

        history_sorted  = sorted(history, key=lambda x: x['timestamp'], reverse=True)
        history_limited = history_sorted[:limit]

        return {
            'success': True,
            'data': {
                'total_records':     len(history),
                'displayed_records': len(history_limited),
                'records':           history_limited,
            }
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return {'success': False, 'error': str(e)}


@router.get("/history/daily")
def get_daily_history(days: int = Query(90, ge=1, le=365)):
    """
    Return pre-computed per-day uptime data from Supabase for the 90-day bar chart.
    Each row: { date, total_checks, down_checks, downtime_minutes, status }.
    Returns empty list when Supabase is not configured (dashboard falls back to event-based bars).
    """
    try:
        if not monitor_service.db.is_available():
            return {'success': True, 'data': [], 'source': 'unavailable'}
        rows = monitor_service.db.get_daily(days=days)
        return {'success': True, 'data': rows, 'source': 'supabase'}
    except Exception as e:
        logger.error(f"Error getting daily history: {e}")
        return {'success': False, 'error': str(e), 'data': []}


@router.get("/logs/history")
def get_log_history(days: int = Query(4, ge=1, le=7)):
    """
    Return all stored log lines from Supabase for the last N days.
    Used by the Live Server Logs box to show historical data beyond the 30-min Render window.
    """
    try:
        if not monitor_service.db.is_available():
            return {'success': True, 'data': [], 'source': 'unavailable'}
        logs = monitor_service.db.get_logs(days=days)
        return {'success': True, 'data': logs, 'total': len(logs), 'days': days}
    except Exception as e:
        logger.error(f"Error getting log history: {e}")
        return {'success': False, 'error': str(e), 'data': []}


@router.get("/logs/errors")
def get_error_logs(days: int = Query(30, ge=1, le=30)):
    """
    Return stored error/warn log lines from Supabase (last N days, up to 30).
    Used by the Errors & Warnings section of the logs page.
    """
    try:
        if not monitor_service.db.is_available():
            return {'success': True, 'data': [], 'source': 'unavailable'}
        logs = monitor_service.db.get_error_logs(days=days)
        return {'success': True, 'data': logs, 'total': len(logs), 'days': days}
    except Exception as e:
        logger.error(f"Error getting error logs: {e}")
        return {'success': False, 'error': str(e), 'data': []}


@router.get("/services/{service_id}/events")
def get_service_events(service_id: str, days: int = Query(90, ge=1, le=365)):
    """Return stored events (DEGRADED, FAILED, etc.) for a specific service card."""
    try:
        if not monitor_service.db.is_available():
            return {'success': True, 'data': []}
        events = monitor_service.db.get_service_events(service_id, days=days)
        return {'success': True, 'data': events}
    except Exception as e:
        logger.error(f"Error getting service events for {service_id}: {e}")
        return {'success': False, 'error': str(e), 'data': []}


@router.get("/services/degraded")
def get_degraded_services():
    """Return the set of service keys currently degraded based on log error spikes."""
    try:
        degraded = list(monitor_service.degraded_services)
        return {'success': True, 'data': degraded}
    except Exception as e:
        return {'success': False, 'error': str(e), 'data': []}


@router.get("/services/health")
def get_services_health():
    """
    Proxy: fetches per-service health from the AI backend server-to-server.
    Results cached for 5 minutes.
    """
    global _svc_health_cache, _svc_health_ts

    if _svc_health_cache and (_time.monotonic() - _svc_health_ts) < _SVC_HEALTH_TTL:
        return {**_svc_health_cache, "cached": True}

    ai_url = settings.AI_BACKEND_URL
    if not ai_url:
        return {'success': False, 'error': 'AI_BACKEND_URL not configured', 'data': {}}

    try:
        res = _requests.get(f"{ai_url}/api/health/services", timeout=15)
        res.raise_for_status()
        data = res.json()
        _svc_health_cache = data
        _svc_health_ts = _time.monotonic()
        logger.info("Fetched per-service health from AI backend")
        return data
    except Exception as e:
        logger.error(f"Failed to fetch AI backend health: {e}")
        return {'success': False, 'error': str(e), 'data': {}}



@router.get("/health")
async def health_check():
    try:
        return {'success': True, 'status': 'healthy', 'timestamp': datetime.now().isoformat()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.post("/monitor/check")
async def trigger_manual_check():
    try:
        status_changed, current_status = monitor_service.check_and_update_status()
        current = monitor_service.get_current_status()
        return {
            'success': True,
            'data': {
                'status_changed':    status_changed,
                'current_status':    current_status,
                'current_snapshot':  current.to_dict()
            }
        }
    except Exception as e:
        logger.error(f"Error triggering manual check: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/logs/clear-errors")
def clear_error_logs():
    """Clear all stored log lines from monitor_logs (leaves events/daily/state intact)."""
    try:
        if monitor_service.db.is_available():
            monitor_service.db.clear_logs()
        return {'success': True, 'message': 'Error logs cleared'}
    except Exception as e:
        logger.error(f"Error clearing error logs: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/monitor/clear-logs")
def clear_logs():
    """Clear all event logs, daily data, stored error logs, and reset state."""
    try:
        monitor_service.clear_all_data()
        logger.info("All data cleared by user")
        return {
            'success': True,
            'message': 'All logs and state cleared successfully',
            'data': {
                'cleared_at': datetime.now().isoformat(),
                'supabase':   monitor_service.db.is_available(),
            }
        }
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return {'success': False, 'error': str(e)}
