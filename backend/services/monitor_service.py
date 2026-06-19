import os
import json
from datetime import datetime
from backend.services.render_checker import RenderChecker
from backend.services.email_service import EmailService
from backend.database.csv_handler import CSVHandler
from backend.database.supabase_handler import SupabaseHandler
from backend.database.models import ServiceStatusRecord, ServiceStatusSnapshot
from backend.utils.logger import logger
from backend.utils.helpers import get_current_timestamp, calculate_duration
from backend.config.settings import settings

# Deploy restarts on Render take ~30–90s. Only log/alert after this grace period.
GRACE_PERIOD_MINUTES = 2


class MonitorService:
    """Core service for monitoring and managing service status."""

    STATE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'backend', 'data', 'state.json'
    )

    def __init__(self):
        self.render_checker = RenderChecker()
        self.email_service  = EmailService()
        self.csv_handler    = CSVHandler(settings.CSV_FILE_PATH)
        self.db             = SupabaseHandler(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.current_state  = self._load_state()

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self):
        # DB is the primary source — survives redeploys
        if self.db.is_available():
            state = self.db.get_state()
            if state:
                state.setdefault('recovery_email_sent', False)
                state.setdefault('failure_confirmed', True)
                state.setdefault('failure_issue_type', 'NONE')
                logger.info("State loaded from Supabase")
                return state

        # Fall back to local JSON (lost on Render restart but fine for dev)
        try:
            with open(self.STATE_FILE, 'r') as f:
                state = json.load(f)
            state.setdefault('recovery_email_sent', False)
            state.setdefault('failure_confirmed', True)
            state.setdefault('failure_issue_type', 'NONE')
            return state
        except FileNotFoundError:
            return self._create_default_state()
        except Exception as e:
            logger.warning(f"Error loading state: {e}, using default")
            return self._create_default_state()

    def _create_default_state(self):
        return {
            'is_running':          True,
            'last_status':         'RUNNING',
            'last_check_time':     get_current_timestamp(),
            'failure_start_time':  None,
            'last_recovery_time':  None,
            'email_alert_sent':    False,
            'recovery_email_sent': False,
            'failure_confirmed':   True,
            'failure_issue_type':  'NONE',
        }

    def _save_state(self):
        # Save to DB (persists across redeploys)
        if self.db.is_available():
            self.db.save_state(self.current_state)
        # Always write local JSON as an in-process backup
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.current_state, f)
        except Exception as e:
            logger.error(f"Error saving state JSON: {e}")

    # ── Core check logic ─────────────────────────────────────────────────────

    def check_and_update_status(self, service_name='Render Service'):
        """
        Check service status and update state.
        Returns tuple: (status_changed, current_status)
        """
        try:
            current_time = get_current_timestamp()  # set first so it's always available in except
            is_running, issue_type, error_msg = self.render_checker.check_service_status()

            logger.info(f"Service check result: running={is_running}, issue={issue_type}")

            # Persist daily uptime data (1 check = 1 minute interval)
            today = datetime.now().date().isoformat()
            downtime_add = 1.0 if not is_running else 0.0
            self.db.upsert_daily(today, is_running, downtime_add)

            # Store error/warn log lines; also purge old DB records (once per day)
            self._store_error_logs()
            self.db.purge_old_records()

            previous_running  = self.current_state['is_running']
            failure_confirmed = self.current_state.get('failure_confirmed', True)

            if is_running:
                if not previous_running:
                    return self._handle_service_recovery(service_name, current_time)
                self.current_state['last_check_time'] = current_time
                self._save_state()
                return (False, 'RUNNING')

            # Service is down
            if previous_running:
                return self._start_grace_period(service_name, current_time, issue_type)

            if not failure_confirmed:
                return self._evaluate_grace_period(service_name, current_time, issue_type)

            self.current_state['last_check_time'] = current_time
            self._save_state()
            return (False, 'FAILED')

        except Exception as e:
            logger.error(f"Error in check_and_update_status: {e}")
            self.current_state['last_check_time'] = current_time
            return (False, self.current_state.get('last_status', 'UNKNOWN'))

    def _store_error_logs(self):
        """Store all log lines from the last Render fetch (deduped by id, 30-day retention)."""
        if not self.db.is_available():
            return
        try:
            logs = self.render_checker.fetch_recent()   # uses cache — no extra API call
            if logs:
                self.db.add_logs(logs)
        except Exception as exc:
            logger.error(f"Failed to store logs: {exc}")

    def _start_grace_period(self, service_name, failure_time, issue_type):
        logger.warning(
            f"Service DOWN at {failure_time} — grace period started "
            f"({GRACE_PERIOD_MINUTES}m before logging)"
        )
        self.current_state.update({
            'is_running':          False,
            'last_status':         'FAILED',
            'failure_start_time':  failure_time,
            'last_check_time':     failure_time,
            'failure_confirmed':   False,
            'failure_issue_type':  issue_type,
            'email_alert_sent':    False,
            'recovery_email_sent': False,
        })
        self._save_state()
        return (False, 'FAILED')

    def _evaluate_grace_period(self, service_name, current_time, issue_type):
        failure_start   = self.current_state.get('failure_start_time')
        downtime_so_far = calculate_duration(failure_start, current_time) if failure_start else 0

        self.current_state['last_check_time'] = current_time

        if downtime_so_far >= GRACE_PERIOD_MINUTES:
            logger.warning(
                f"Grace period expired ({downtime_so_far:.1f}m) — confirming real outage"
            )
            return self._confirm_outage(
                service_name,
                failure_start or current_time,
                self.current_state.get('failure_issue_type', issue_type),
            )

        logger.info(
            f"Service still down — grace period active "
            f"({downtime_so_far:.1f}/{GRACE_PERIOD_MINUTES}m)"
        )
        self._save_state()
        return (False, 'FAILED')

    def _confirm_outage(self, service_name, failure_time, issue_type):
        self.current_state['failure_confirmed'] = True

        record = ServiceStatusRecord(
            id=self.csv_handler.generate_unique_id(),
            timestamp=failure_time,
            service_name=service_name,
            status='FAILED',
            issue_type=issue_type,
            duration=0,
            resolved_at=None
        )
        if self.db.is_available():
            self.db.add_event(record)
        else:
            self.csv_handler.add_record(record)

        if not self.current_state.get('email_alert_sent'):
            if self.email_service.send_service_down_alert(service_name, failure_time, issue_type):
                self.current_state['email_alert_sent'] = True
                logger.info("Down alert email sent")

        self._save_state()
        logger.info(f"Real outage confirmed and recorded: {record.id}")
        return (True, 'FAILED')

    def _handle_service_recovery(self, service_name, recovery_time):
        failure_confirmed = self.current_state.get('failure_confirmed', True)

        if not failure_confirmed:
            logger.info(
                "Service recovered within grace period — "
                "treating as deploy restart, no log or email"
            )
            self.current_state.update({
                'is_running':          True,
                'last_status':         'RUNNING',
                'last_check_time':     recovery_time,
                'failure_start_time':  None,
                'failure_confirmed':   True,
                'email_alert_sent':    False,
                'recovery_email_sent': False,
            })
            self._save_state()
            return (False, 'RUNNING')

        if self.current_state.get('recovery_email_sent'):
            logger.info("Recovery email already sent — skipping duplicate")
            self.current_state.update({
                'is_running':      True,
                'last_status':     'RUNNING',
                'last_check_time': recovery_time,
            })
            self._save_state()
            return (True, 'RUNNING')

        failure_start    = self.current_state.get('failure_start_time')
        downtime_minutes = calculate_duration(failure_start, recovery_time) if failure_start else 0

        self.current_state.update({
            'is_running':          True,
            'last_status':         'RUNNING',
            'last_recovery_time':  recovery_time,
            'last_check_time':     recovery_time,
            'failure_start_time':  None,
            'failure_confirmed':   True,
            'email_alert_sent':    False,
            'recovery_email_sent': True,
        })

        record = ServiceStatusRecord(
            id=self.csv_handler.generate_unique_id(),
            timestamp=recovery_time,
            service_name=service_name,
            status='RECOVERED',
            issue_type='NONE',
            duration=downtime_minutes,
            resolved_at=recovery_time
        )
        if self.db.is_available():
            self.db.add_event(record)
        else:
            self.csv_handler.add_record(record)

        if self.email_service.send_service_recovered_alert(service_name, recovery_time, downtime_minutes):
            logger.info("Recovery alert email sent")

        self._save_state()
        logger.info(f"Service recovery recorded: {record.id}, downtime: {downtime_minutes:.1f}m")
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

    def get_history(self, days: int = 90):
        """Return FAILED/RECOVERED events. Prefers DB; falls back to CSV."""
        try:
            if self.db.is_available():
                events = self.db.get_events(days=days)
                return [{
                    'id':           e.get('id', ''),
                    'timestamp':    e.get('timestamp', ''),
                    'service_name': e.get('service_name', ''),
                    'status':       e.get('status', ''),
                    'issue_type':   e.get('issue_type', ''),
                    'duration':     e.get('duration', 0),
                    'resolved_at':  e.get('resolved_at') or '',
                } for e in events]
            records = self.csv_handler.read_all_records()
            return [r.to_dict() for r in records]
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def reset_state(self):
        self.current_state = self._create_default_state()
        self._save_state()
        if self.db.is_available():
            self.db.reset_state()
        logger.info("Monitor state reset")

    def clear_all_data(self):
        """Clear all stored data — events, daily, logs — and reset state."""
        if self.db.is_available():
            self.db.clear_events()
            self.db.clear_daily()
            self.db.clear_logs()
            self.db.reset_state()
        self.csv_handler.clear_all_records()
        self.current_state = self._create_default_state()
        self._save_state()
        logger.info("All monitor data cleared")


# ── Singleton ────────────────────────────────────────────────────────────────

_monitor_instance = None


def get_monitor_service():
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = MonitorService()
    return _monitor_instance
