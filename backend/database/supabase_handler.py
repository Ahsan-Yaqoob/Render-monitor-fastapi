"""
Supabase database handler — persists monitor state, events, daily bar data, and error logs.

Falls back gracefully: if SUPABASE_URL / SUPABASE_KEY are not set, or if the supabase
package is not installed, is_available() returns False and every method is a no-op.
The monitor then continues using the CSV / state.json fallback.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client as _SupabaseClient  # type: ignore
    _PKG_OK = True
except ImportError:
    _SupabaseClient = None  # type: ignore
    _PKG_OK = False

_STATE_ROW_ID = 1          # monitor_state always has exactly one row
_EVENTS_DAYS  = 30         # purge events older than this
_DAILY_DAYS   = 90         # purge daily rows older than this
_LOGS_DAYS       = 4       # purge regular (info) log lines older than 4 days
_ERROR_LOGS_DAYS = 30      # keep error/warning log lines for 30 days

_purge_done_for: str = ''  # date string — run purge at most once per day


class SupabaseHandler:
    def __init__(self, url: str | None, key: str | None):
        self._client = None
        if not _PKG_OK:
            logger.warning("supabase package not installed — database persistence disabled. "
                           "Run: pip install supabase")
            return
        if not url or not key:
            logger.info("SUPABASE_URL / SUPABASE_KEY not set — using file-based fallback")
            return
        try:
            self._client = create_client(url, key)
            logger.info("Supabase client ready")
        except Exception as exc:
            logger.error(f"Supabase init failed: {exc}")

    def is_available(self) -> bool:
        return self._client is not None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _c(self):
        return self._client

    # ── State (replaces state.json) ───────────────────────────────────────────

    def get_state(self) -> dict | None:
        if not self._client:
            return None
        try:
            res = self._client.table('monitor_state').select('*').eq('id', _STATE_ROW_ID).execute()
            if not res.data:
                return None
            row = res.data[0]
            return {
                'is_running':           row.get('is_running', True),
                'last_status':          row.get('last_status', 'RUNNING'),
                'last_check_time':      row.get('last_check_time'),
                'failure_start_time':   row.get('failure_start_time'),
                'last_recovery_time':   row.get('last_recovery_time'),
                'email_alert_sent':     row.get('email_alert_sent', False),
                'recovery_email_sent':  row.get('recovery_email_sent', False),
                'failure_confirmed':    row.get('failure_confirmed', True),
                'failure_issue_type':   row.get('failure_issue_type', 'NONE'),
            }
        except Exception as exc:
            logger.error(f"DB get_state: {exc}")
            return None

    def save_state(self, state: dict) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_state').upsert({
                'id':                   _STATE_ROW_ID,
                'is_running':           state.get('is_running', True),
                'last_status':          state.get('last_status', 'RUNNING'),
                'last_check_time':      state.get('last_check_time'),
                'failure_start_time':   state.get('failure_start_time'),
                'last_recovery_time':   state.get('last_recovery_time'),
                'email_alert_sent':     state.get('email_alert_sent', False),
                'recovery_email_sent':  state.get('recovery_email_sent', False),
                'failure_confirmed':    state.get('failure_confirmed', True),
                'failure_issue_type':   state.get('failure_issue_type', 'NONE'),
            }, on_conflict='id').execute()
        except Exception as exc:
            logger.error(f"DB save_state: {exc}")

    def reset_state(self) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_state').upsert({
                'id':                   _STATE_ROW_ID,
                'is_running':           True,
                'last_status':          'RUNNING',
                'last_check_time':      datetime.now(timezone.utc).isoformat(),
                'failure_start_time':   None,
                'last_recovery_time':   None,
                'email_alert_sent':     False,
                'recovery_email_sent':  False,
                'failure_confirmed':    True,
                'failure_issue_type':   'NONE',
            }, on_conflict='id').execute()
        except Exception as exc:
            logger.error(f"DB reset_state: {exc}")

    # ── Events (replaces logs.csv) ────────────────────────────────────────────

    def add_event(self, record) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_events').upsert({
                'id':           record.id,
                'timestamp':    record.timestamp,
                'service_name': record.service_name,
                'status':       record.status,
                'issue_type':   record.issue_type,
                'duration':     record.duration,
                'resolved_at':  record.resolved_at,
            }, on_conflict='id').execute()
        except Exception as exc:
            logger.error(f"DB add_event: {exc}")

    def get_events(self, days: int = 30, limit: int = 5000) -> list[dict]:
        if not self._client:
            return []
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            res = (self._client.table('monitor_events')
                   .select('*')
                   .gte('timestamp', cutoff)
                   .order('timestamp', desc=True)
                   .limit(limit)
                   .execute())
            return res.data or []
        except Exception as exc:
            logger.error(f"DB get_events: {exc}")
            return []

    def clear_events(self) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_events').delete().gte('timestamp', '1900-01-01T00:00:00Z').execute()
        except Exception as exc:
            logger.error(f"DB clear_events: {exc}")

    def _purge_old_events(self) -> None:
        if not self._client:
            return
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=_EVENTS_DAYS)).isoformat()
            self._client.table('monitor_events').delete().lt('timestamp', cutoff).execute()
        except Exception as exc:
            logger.error(f"DB purge_old_events: {exc}")

    # ── Daily (90-day bar data) ───────────────────────────────────────────────

    def upsert_daily(self, date_str: str, is_running: bool, downtime_add: float = 0.0) -> None:
        """Increment today's row. Called on every health check (every minute)."""
        if not self._client:
            return
        try:
            res = self._client.table('monitor_daily').select('*').eq('date', date_str).execute()
            if res.data:
                row        = res.data[0]
                new_total  = (row.get('total_checks') or 0) + 1
                new_down   = (row.get('down_checks') or 0) + (0 if is_running else 1)
                new_dt     = (row.get('downtime_minutes') or 0.0) + downtime_add
                new_status = 'up' if new_down == 0 else ('down' if new_dt >= 60 else 'partial')
                self._client.table('monitor_daily').update({
                    'total_checks':     new_total,
                    'down_checks':      new_down,
                    'downtime_minutes': new_dt,
                    'status':           new_status,
                }).eq('date', date_str).execute()
            else:
                self._client.table('monitor_daily').insert({
                    'date':             date_str,
                    'total_checks':     1,
                    'down_checks':      0 if is_running else 1,
                    'downtime_minutes': downtime_add,
                    'status':           'up' if is_running else 'partial',
                }).execute()
        except Exception as exc:
            logger.error(f"DB upsert_daily: {exc}")

    def get_daily(self, days: int = 90) -> list[dict]:
        if not self._client:
            return []
        try:
            cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
            res = (self._client.table('monitor_daily')
                   .select('*')
                   .gte('date', cutoff)
                   .order('date', desc=False)
                   .execute())
            return res.data or []
        except Exception as exc:
            logger.error(f"DB get_daily: {exc}")
            return []

    def clear_daily(self) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_daily').delete().gte('date', '1900-01-01').execute()
        except Exception as exc:
            logger.error(f"DB clear_daily: {exc}")

    def _purge_old_daily(self) -> None:
        if not self._client:
            return
        try:
            cutoff = (datetime.now(timezone.utc).date() - timedelta(days=_DAILY_DAYS)).isoformat()
            self._client.table('monitor_daily').delete().lt('date', cutoff).execute()
        except Exception as exc:
            logger.error(f"DB purge_old_daily: {exc}")

    # ── Log lines (30-day rolling window) ────────────────────────────────────

    def add_logs(self, log_entries: list[dict]) -> None:
        """Store all log lines. Render's log id deduplicates on re-fetch."""
        if not self._client or not log_entries:
            return
        try:
            rows = []
            for e in log_entries:
                log_id = e.get('id')
                if not log_id:
                    log_id = 'gen_' + hashlib.md5(
                        f"{e.get('timestamp','')}{e.get('message','')}".encode()
                    ).hexdigest()[:16]
                rows.append({
                    'id':        log_id,
                    'timestamp': e.get('timestamp'),
                    'level':     e.get('level', 'info'),
                    'message':   e.get('message', ''),
                })
            self._client.table('monitor_logs').upsert(rows, on_conflict='id').execute()
        except Exception as exc:
            logger.error(f"DB add_logs: {exc}")

    def _paginate_logs(self, query_fn, limit: int = 10000) -> list[dict]:
        """Fetch rows in pages of 1000 to work around Supabase's max_rows cap."""
        all_rows: list = []
        page = 1000
        offset = 0
        while len(all_rows) < limit:
            fetch = min(page, limit - len(all_rows))
            res = query_fn(offset, offset + fetch - 1).execute()
            rows = res.data or []
            all_rows.extend(rows)
            if len(rows) < fetch:
                break
            offset += fetch
        return all_rows

    def get_logs(self, days: int = 4, limit: int = 10000) -> list[dict]:
        """Return all stored log lines for the last N days (for the live log history view)."""
        if not self._client:
            return []
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            base = (self._client.table('monitor_logs')
                    .select('*')
                    .gte('timestamp', cutoff)
                    .order('timestamp', desc=True))
            return self._paginate_logs(lambda s, e: base.range(s, e), limit)
        except Exception as exc:
            logger.error(f"DB get_logs: {exc}")
            return []

    def get_error_logs(self, days: int = 30, limit: int = 5000) -> list[dict]:
        """Return only error/warn lines for the last N days (for the Errors & Warnings section)."""
        if not self._client:
            return []
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            base = (self._client.table('monitor_logs')
                    .select('*')
                    .gte('timestamp', cutoff)
                    .in_('level', ['error', 'critical', 'warning', 'warn'])
                    .order('timestamp', desc=True))
            return self._paginate_logs(lambda s, e: base.range(s, e), limit)
        except Exception as exc:
            logger.error(f"DB get_error_logs: {exc}")
            return []

    def clear_logs(self) -> None:
        if not self._client:
            return
        try:
            self._client.table('monitor_logs').delete().gte('timestamp', '1900-01-01T00:00:00Z').execute()
        except Exception as exc:
            logger.error(f"DB clear_logs: {exc}")

    def _purge_old_logs(self) -> None:
        if not self._client:
            return
        try:
            cutoff_all    = (datetime.now(timezone.utc) - timedelta(days=_LOGS_DAYS)).isoformat()
            cutoff_errors = (datetime.now(timezone.utc) - timedelta(days=_ERROR_LOGS_DAYS)).isoformat()
            # Delete regular (info) logs older than 4 days
            (self._client.table('monitor_logs').delete()
                .lt('timestamp', cutoff_all)
                .not_.in_('level', ['error', 'critical', 'warning', 'warn'])
                .execute())
            # Delete error/warning logs older than 30 days
            (self._client.table('monitor_logs').delete()
                .lt('timestamp', cutoff_errors)
                .in_('level', ['error', 'critical', 'warning', 'warn'])
                .execute())
        except Exception as exc:
            logger.error(f"DB purge_old_logs: {exc}")

    # ── Combined daily purge ──────────────────────────────────────────────────

    def purge_old_records(self) -> None:
        """Delete rows past their retention window. Safe to call on every check — runs at most once per day."""
        global _purge_done_for
        today = datetime.now(timezone.utc).date().isoformat()
        if today == _purge_done_for:
            return
        self._purge_old_events()
        self._purge_old_daily()
        self._purge_old_logs()
        _purge_done_for = today
        logger.info("DB: purged old records")
