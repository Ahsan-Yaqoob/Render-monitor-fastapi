from fastapi import APIRouter, Query
from backend.services.monitor_service import get_monitor_service
from backend.database.csv_handler import CSVHandler
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.utils.helpers import format_duration_readable, time_ago
from datetime import datetime
import requests as _requests
import time as _time

# Server-side cache so we don't hammer the AI backend on every frontend refresh
_svc_health_cache: dict = {}
_svc_health_ts: float = 0.0
_SVC_HEALTH_TTL = 300  # 5 minutes

router = APIRouter(prefix="/api", tags=["dashboard"])

monitor_service = get_monitor_service()
csv_handler = CSVHandler(settings.CSV_FILE_PATH)


@router.get("/status")
async def get_status():
    """Get current service status."""
    try:
        status_snapshot = monitor_service.get_current_status()
        
        return {
            'success': True,
            'data': {
                'is_running': status_snapshot.is_running,
                'status': 'RUNNING' if status_snapshot.is_running else 'FAILED',
                'last_check': status_snapshot.last_check_time,
                'last_check_time': status_snapshot.last_check_time,
                'last_check_ago': time_ago(status_snapshot.last_check_time),
                'failure_start': status_snapshot.failure_start_time,
                'last_recovery': status_snapshot.last_recovery_time,
                'downtime_minutes': status_snapshot.current_downtime_minutes,
                'downtime_readable': format_duration_readable(status_snapshot.current_downtime_minutes),
                'issue_type': status_snapshot.issue_type,
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/history")
async def get_history(limit: int = Query(100, ge=1, le=5000), days: int = Query(0, ge=0, le=365)):
    """Get all event history."""
    try:
        history = monitor_service.get_history()
        
        if days > 0:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            history = [
                record for record in history
                if datetime.fromisoformat(record['timestamp']) >= cutoff_date
            ]
        
        history_sorted = sorted(
            history,
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        history_limited = history_sorted[:limit]
        
        return {
            'success': True,
            'data': {
                'total_records': len(history),
                'displayed_records': len(history_limited),
                'records': history_limited
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/services/health")
def get_services_health():
    """
    Proxy: fetches per-service health from the AI backend server-to-server.
    The AI backend URL never reaches the browser — only this monitor backend calls it.
    Results are cached for 5 minutes to avoid hammering the AI backend.
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


@router.get("/render-logs")
def get_render_logs(limit: int = Query(2000, ge=1, le=5000)):
    """
    Return the live server logs for a fixed time window (see render_checker
    log_window_minutes), pulled directly from Render's /v1/logs API. The window is
    time-based, so the span shown stays consistent regardless of log volume.
    Reuses the same 30-second cache the health checker uses.
    """
    checker = monitor_service.render_checker
    logs = checker.fetch_logs()
    return {
        "success": True,
        "data": logs[:limit],
        "total": len(logs),
        "showing": min(limit, len(logs)),
        "window_minutes": checker.log_window_minutes,
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        return {
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@router.post("/monitor/check")
async def trigger_manual_check():
    """Manually trigger a service status check."""
    try:
        status_changed, current_status = monitor_service.check_and_update_status()
        current = monitor_service.get_current_status()
        
        return {
            'success': True,
            'data': {
                'status_changed': status_changed,
                'current_status': current_status,
                'current_snapshot': current.to_dict()
            }
        }
    
    except Exception as e:
        logger.error(f"Error triggering manual check: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.post("/monitor/clear-logs")
async def clear_logs():
    """Clear all event logs and reset service state."""
    try:
        csv_handler.clear_all_records()
        
        # Reset the service state to default
        monitor_service.current_state = monitor_service._create_default_state()
        monitor_service._save_state()
        
        logger.info("All logs and state cleared by user")
        
        return {
            'success': True,
            'message': 'All logs and state cleared successfully',
            'data': {
                'cleared_at': datetime.now().isoformat(),
                'status': 'cleared',
                'state_reset': True
            }
        }
    
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
