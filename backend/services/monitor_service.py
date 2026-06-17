import os
import json
from datetime import datetime
from backend.services.render_checker import RenderChecker
from backend.services.email_service import EmailService
from backend.database.csv_handler import CSVHandler
from backend.database.models import ServiceStatusRecord, ServiceStatusSnapshot
from backend.utils.logger import logger
from backend.utils.helpers import get_current_timestamp, calculate_duration
from backend.config.settings import settings


class MonitorService:
    """Core service for monitoring and managing service status."""

    STATE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'backend', 'data', 'state.json'
    )

    def __init__(self):
        self.render_checker = RenderChecker()
        self.email_service = EmailService()
        self.csv_handler = CSVHandler(settings.CSV_FILE_PATH)
        self.current_state = self._load_state()

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self):
        try:
            with open(self.STATE_FILE, 'r') as f:
                state = json.load(f)
            # Migrate old state files that lack the recovery_email_sent field
            state.setdefault('recovery_email_sent', False)
            return state
        except FileNotFoundError:
            return self._create_default_state()
        except Exception as e:
            logger.warning(f"Error loading state: {e}, using default")
            return self._create_default_state()

    def _create_default_state(self):
        return {
            'is_running': True,
            'last_status': 'RUNNING',
            'last_check_time': get_current_timestamp(),
            'failure_start_time': None,
            'last_recovery_time': None,
            'email_alert_sent': False,
            'recovery_email_sent': False,
        }

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.current_state, f)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    # ── Core check logic ─────────────────────────────────────────────────────

    def check_and_update_status(self, service_name='Render Service'):
        """
        Check service status and update state.
        Returns tuple: (status_changed, current_status)
        """
        try:
            is_running, issue_type, error_msg = self.render_checker.check_service_status()
            current_time = get_current_timestamp()

            logger.info(f"Service check result: running={is_running}, issue={issue_type}")

            previous_state = self.current_state['is_running']

            if is_running and not previous_state:
                return self._handle_service_recovery(service_name, current_time)

            elif not is_running and previous_state:
                return self._handle_service_failure(service_name, current_time, issue_type)

            else:
                # No state change — update timestamp only
                self.current_state['last_check_time'] = current_time
                self._save_state()
                return (False, 'RUNNING' if is_running else 'FAILED')

        except Exception as e:
            logger.error(f"Error in check_and_update_status: {e}")
            return (False, self.current_state.get('last_status', 'UNKNOWN'))

    def _handle_service_failure(self, service_name, failure_time, issue_type):
        """Handle service going down — send DOWN email once."""
        logger.warning(f"Service DOWN detected at {failure_time}")

        self.current_state['is_running'] = False
        self.current_state['last_status'] = 'FAILED'
        self.current_state['failure_start_time'] = failure_time
        self.current_state['last_check_time'] = failure_time
        self.current_state['email_alert_sent'] = False
        self.current_state['recovery_email_sent'] = False

        record = ServiceStatusRecord(
            id=self.csv_handler.generate_unique_id(),
            timestamp=failure_time,
            service_name=service_name,
            status='FAILED',
            issue_type=issue_type,
            duration=0,
            resolved_at=None
        )
        self.csv_handler.add_record(record)

        if not self.current_state['email_alert_sent']:
            if self.email_service.send_service_down_alert(service_name, failure_time, issue_type):
                self.current_state['email_alert_sent'] = True
                logger.info("Down alert email sent")

        self._save_state()
        logger.info(f"Service failure recorded: {record.id}")
        return (True, 'FAILED')

    def _handle_service_recovery(self, service_name, recovery_time):
        """Handle service coming back up — send RECOVERY email once per outage."""
        logger.warning(f"Service RECOVERED detected at {recovery_time}")

        # Guard: only send recovery email once per outage cycle
        if self.current_state.get('recovery_email_sent'):
            logger.info("Recovery email already sent for this outage — skipping duplicate")
            self.current_state['is_running'] = True
            self.current_state['last_status'] = 'RUNNING'
            self.current_state['last_check_time'] = recovery_time
            self._save_state()
            return (True, 'RUNNING')

        failure_start = self.current_state.get('failure_start_time')
        downtime_minutes = calculate_duration(failure_start, recovery_time) if failure_start else 0

        self.current_state['is_running'] = True
        self.current_state['last_status'] = 'RUNNING'
        self.current_state['last_recovery_time'] = recovery_time
        self.current_state['last_check_time'] = recovery_time
        self.current_state['email_alert_sent'] = False
        self.current_state['recovery_email_sent'] = True
        self.current_state['failure_start_time'] = None

        record = ServiceStatusRecord(
            id=self.csv_handler.generate_unique_id(),
            timestamp=recovery_time,
            service_name=service_name,
            status='RECOVERED',
            issue_type='NONE',
            duration=downtime_minutes,
            resolved_at=recovery_time
        )
        self.csv_handler.add_record(record)

        if self.email_service.send_service_recovered_alert(service_name, recovery_time, downtime_minutes):
            logger.info("Recovery alert email sent")

        self._save_state()
        logger.info(f"Service recovery recorded: {record.id}, downtime: {downtime_minutes:.1f} min")
        return (True, 'RUNNING')

    # ── Status & history ─────────────────────────────────────────────────────

    def get_current_status(self):
        try:
            current_downtime = 0
            if not self.current_state['is_running'] and self.current_state.get('failure_start_time'):
                current_downtime = calculate_duration(
                    self.current_state['failure_start_time'],
                    get_current_timestamp()
                )

            return ServiceStatusSnapshot(
                is_running=self.current_state['is_running'],
                last_status=self.current_state['last_status'],
                last_check_time=self.current_state['last_check_time'],
                failure_start_time=self.current_state.get('failure_start_time'),
                last_recovery_time=self.current_state.get('last_recovery_time'),
                current_downtime_minutes=current_downtime,
                issue_type='NONE' if self.current_state['is_running'] else 'SERVICE_DOWN'
            )
        except Exception as e:
            logger.error(f"Error getting current status: {e}")
            return ServiceStatusSnapshot(
                is_running=True,
                last_status='RUNNING',
                last_check_time=get_current_timestamp(),
                current_downtime_minutes=0,
                issue_type='NONE'
            )

    def get_history(self):
        try:
            records = self.csv_handler.read_all_records()
            return [record.to_dict() for record in records]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def reset_state(self):
        self.current_state = self._create_default_state()
        self._save_state()
        logger.info("Monitor state reset")


# ── Singleton ────────────────────────────────────────────────────────────────

_monitor_instance = None


def get_monitor_service():
    """Return the shared MonitorService singleton."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = MonitorService()
    return _monitor_instance
