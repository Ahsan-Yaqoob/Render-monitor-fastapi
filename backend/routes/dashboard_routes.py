from fastapi import APIRouter, Query
from backend.services.monitor_service import get_monitor_service
from backend.services.stats_service import StatsService
from backend.database.csv_handler import CSVHandler
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.utils.helpers import format_duration_readable, time_ago
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api", tags=["dashboard"])

monitor_service = get_monitor_service()
csv_handler = CSVHandler(settings.CSV_FILE_PATH)
stats_service = StatsService(csv_handler)


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
                'ai_backend_url': settings.AI_BACKEND_URL,
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/history")
async def get_history(limit: int = Query(100, ge=1, le=1000), days: int = Query(0, ge=0, le=365)):
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


@router.get("/stats")
async def get_stats(days: int = Query(30, ge=0, le=365)):
    """Get comprehensive statistics."""
    try:
        if days == 0:
            stats = stats_service.get_all_stats()
        else:
            stats = stats_service.get_stats_by_period(days=days)
        
        return {
            'success': True,
            'data': stats.to_dict()
        }
    
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/stats/daily-failures")
async def get_daily_failures(days: int = Query(30, ge=1, le=365)):
    """Get daily failure counts."""
    try:
        daily_failures = stats_service.get_daily_failures(days=days)
        
        return {
            'success': True,
            'data': daily_failures
        }
    
    except Exception as e:
        logger.error(f"Error getting daily failures: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/stats/issue-frequency")
async def get_issue_frequency():
    """Get issue type frequency."""
    try:
        issue_freq = stats_service.get_issue_frequency()
        
        return {
            'success': True,
            'data': issue_freq
        }
    
    except Exception as e:
        logger.error(f"Error getting issue frequency: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/stats/downtime-by-issue")
async def get_downtime_by_issue():
    """Get total downtime grouped by issue type."""
    try:
        downtime_data = stats_service.get_downtime_by_issue()
        
        formatted_data = {
            issue: format_duration_readable(minutes)
            for issue, minutes in downtime_data.items()
        }
        
        return {
            'success': True,
            'data': formatted_data
        }
    
    except Exception as e:
        logger.error(f"Error getting downtime by issue: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/stats/recovery-time-avg")
async def get_recovery_time_avg():
    """Get average recovery time."""
    try:
        avg_recovery = stats_service.get_recovery_time_avg()
        
        return {
            'success': True,
            'data': {
                'average_recovery_minutes': avg_recovery,
                'average_recovery_readable': format_duration_readable(avg_recovery)
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting recovery time: {str(e)}")
        return {
            'success': False,
            'error': str(e)
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
