import requests
import time as _time
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.database.models import IssueType

# Shared log cache — used by both health checks and the /api/render-logs endpoint.
_LOG_CACHE: list = []
_LOG_CACHE_TS: float = 0.0
_LOG_CACHE_TTL: int = 30    # seconds
_LOG_FETCH_LIMIT: int = 200

# Owner id is required by the /v1/logs endpoint; it never changes, so fetch once.
_OWNER_ID: str | None = None


class RenderChecker:
    """Determines service health from Render logs, with URL fallback if logs are unavailable."""

    def __init__(self):
        self.api_key    = settings.RENDER_API_KEY
        self.service_id = settings.RENDER_SERVICE_ID
        self.api_url    = settings.RENDER_API_URL
        self.headers    = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept":        "application/json",
        }

    # ── Log fetching ─────────────────────────────────────────────────────────

    def _get_owner_id(self) -> str | None:
        """Owner/team id for the service — required by /v1/logs. Cached after first lookup."""
        global _OWNER_ID
        if _OWNER_ID:
            return _OWNER_ID
        data = self._get_service_data()
        if data:
            _OWNER_ID = data.get("ownerId")
        return _OWNER_ID

    @staticmethod
    def _normalize(entry: dict) -> dict:
        """Flatten a Render /v1/logs entry into {timestamp, level, type, message}."""
        labels = {l.get("name"): l.get("value") for l in entry.get("labels", [])}
        return {
            "id":        entry.get("id"),
            "timestamp": entry.get("timestamp"),
            "level":     labels.get("level", "info"),
            "type":      labels.get("type", ""),
            "message":   entry.get("message", ""),
        }

    def fetch_logs(self, force: bool = False) -> list:
        """
        Fetch recent logs from Render's /v1/logs endpoint, cached for _LOG_CACHE_TTL seconds.
        Returns a list of normalized entries, newest first. Empty list on failure.
        """
        global _LOG_CACHE, _LOG_CACHE_TS

        if not force and _LOG_CACHE and (_time.monotonic() - _LOG_CACHE_TS) < _LOG_CACHE_TTL:
            return _LOG_CACHE

        owner = self._get_owner_id()
        if not owner:
            logger.warning("Could not resolve Render ownerId — cannot fetch logs")
            return _LOG_CACHE

        try:
            r = requests.get(
                f"{self.api_url}/logs",
                headers=self.headers,
                params={"ownerId": owner, "resource": self.service_id, "limit": _LOG_FETCH_LIMIT},
                timeout=15,
            )
            r.raise_for_status()
            raw  = r.json()
            logs = [self._normalize(e) for e in raw.get("logs", [])]
            # newest first for display + analysis
            logs.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
            _LOG_CACHE    = logs
            _LOG_CACHE_TS = _time.monotonic()
            logger.info(f"Fetched {len(logs)} log lines from Render")
            return logs
        except Exception as e:
            logger.error(f"Failed to fetch Render logs: {e}")
            return _LOG_CACHE   # return stale cache rather than crashing

    # ── Log analysis ─────────────────────────────────────────────────────────

    _STARTUP_OK = [
        "application startup complete",
        "uvicorn running on",
        "started server process",
        "your service is live",
    ]

    _CRASH = [
        "application startup failed",
        "exited with status",
        "exited with code",
        "traceback (most recent call last)",
        "exception in asgi",
        "killed",
        "out of memory",
        "ran out of memory",
    ]

    def _text(self, entry: dict) -> str:
        return (entry.get("message") or "").lower()

    def analyse_logs(self, logs: list) -> tuple[bool, str, str]:
        """
        Analyse normalized log entries (newest-first) to determine service health.
        Returns (is_running, issue_type, detail).
        """
        if not logs:
            return True, IssueType.UNKNOWN.value, "No logs available"

        chrono = list(reversed(logs))   # oldest -> newest

        # Find last successful startup
        last_startup = -1
        for i, e in enumerate(chrono):
            if any(p in self._text(e) for p in self._STARTUP_OK):
                last_startup = i

        # Look for crashes AFTER the last startup
        window = chrono[last_startup + 1:] if last_startup >= 0 else chrono
        for e in window:
            t = self._text(e)
            if any(p in t for p in self._CRASH):
                raw = (e.get("message") or "")[:150]
                if "out of memory" in t or "killed" in t:
                    return False, "MEMORY_ERROR", f"OOM / process killed: {raw}"
                if "startup failed" in t:
                    return False, "STARTUP_ERROR", f"Startup failed: {raw}"
                return False, "APPLICATION_ERROR", f"Crash detected: {raw}"

        if last_startup >= 0:
            return True, "NONE", "OK - startup confirmed in logs"

        # No startup line — check for active HTTP request logs
        recent = chrono[-50:]
        has_requests = any(
            ('"get '  in self._text(e) or
             '"post ' in self._text(e) or
             '"put '  in self._text(e))
            for e in recent
        )
        if has_requests:
            return True, "NONE", "OK - active request logs"

        return True, "NONE", "OK - no crash patterns in recent logs"

    # ── URL fallback ──────────────────────────────────────────────────────────

    def _check_url(self, url: str) -> tuple[bool, str, str]:
        """HTTP health check — used only if the logs API is unreachable."""
        try:
            r = requests.get(url, timeout=15, allow_redirects=True)
            if r.status_code < 500:
                return True, "NONE", f"OK - HTTP {r.status_code}"
            return False, IssueType.HTTP_ERROR.value, f"HTTP {r.status_code}"
        except requests.Timeout:
            return False, IssueType.TIMEOUT.value, "Request timeout"
        except requests.ConnectionError:
            return False, IssueType.CONNECTION_ERROR.value, "Connection error"
        except Exception as e:
            return False, IssueType.UNKNOWN.value, str(e)

    # ── Main health check ─────────────────────────────────────────────────────

    def check_service_status(self) -> tuple[bool, str, str]:
        """
        Determine service health.
        1. Check Render API metadata for manual suspension.
        2. Analyse the live Render logs.
        3. If logs can't be fetched, fall back to an HTTP health check on the URL.
        Returns (is_running, issue_type, detail_message).
        """
        data = self._get_service_data()

        if data and data.get("suspended") == "suspended":
            logger.warning("Service is manually suspended on Render")
            return False, IssueType.HTTP_ERROR.value, "Service is suspended on Render"

        logs = self.fetch_logs()
        if logs:
            is_running, issue_type, detail = self.analyse_logs(logs)
            logger.info(f"Log analysis -> running={is_running} | {issue_type} | {detail}")
            return is_running, issue_type, detail

        # Logs unavailable — fall back to URL check
        logger.info("Logs unavailable, using URL health check")
        service_url = self._get_service_url(data) if data else None
        if not service_url:
            return False, IssueType.UNKNOWN.value, "Service URL not found in Render API"
        return self._check_url(service_url)

    # ── Metadata helpers ──────────────────────────────────────────────────────

    def _get_service_data(self):
        try:
            r = requests.get(
                f"{self.api_url}/services/{self.service_id}",
                headers=self.headers,
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()

            # Detailed diagnostics so misconfiguration is obvious in the deploy logs
            sid = self.service_id or ""
            masked_id = f"{sid[:8]}…{sid[-4:]}" if len(sid) > 12 else sid
            key_set = "set" if self.api_key else "MISSING"
            if r.status_code == 401:
                logger.error(
                    f"Render API 401 Unauthorized — RENDER_API_KEY is invalid/expired ({key_set})"
                )
            elif r.status_code == 404:
                logger.error(
                    f"Render API 404 — RENDER_SERVICE_ID not found or not owned by this key. "
                    f"service_id='{masked_id}' (len={len(sid)}), api_key={key_set}. "
                    f"Check for stray quotes/spaces in the dashboard env vars."
                )
            else:
                logger.warning(f"Render API returned HTTP {r.status_code}: {r.text[:120]}")
            return None
        except Exception as e:
            logger.error(f"Error fetching service data: {e}")
            return None

    def _get_service_url(self, data: dict) -> str | None:
        if not data:
            return None
        return data.get("serviceDetails", {}).get("url")

    def get_service_info(self):
        data = self._get_service_data()
        if not data:
            return None
        return {
            "id":         data.get("id"),
            "name":       data.get("name"),
            "type":       data.get("type"),
            "suspended":  data.get("suspended"),
            "created_at": data.get("createdAt"),
            "updated_at": data.get("updatedAt"),
            "url":        self._get_service_url(data),
        }

    def validate_credentials(self):
        try:
            r = requests.get(
                f"{self.api_url}/services/{self.service_id}",
                headers=self.headers,
                timeout=5,
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Error validating credentials: {e}")
            return False
