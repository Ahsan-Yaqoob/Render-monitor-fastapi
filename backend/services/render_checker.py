import os
import datetime
import requests
import time as _time
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.database.models import IssueType

# Windowed-log cache — feeds the /api/render-logs DISPLAY (paginated, expensive).
_LOG_CACHE: list = []
_LOG_CACHE_TS: float = 0.0
_LOG_CACHE_TTL: int = 60    # seconds — longer cache keeps us well under Render's rate limit

# Recent-log cache — feeds the HEALTH CHECK (single call, cheap). The health check only
# needs the latest lines to judge liveness, so it never paginates the whole window.
_RECENT_CACHE: list = []
_RECENT_CACHE_TS: float = 0.0
_RECENT_CACHE_TTL: int = 25  # seconds — dedupes scheduler + manual checks
_RECENT_LIMIT: int = 100     # newest N lines (Render caps a single request at 100)

# We fetch a fixed TIME WINDOW (not a fixed line count) for the display so the span shown
# stays consistent: a quiet 30 minutes and a busy 30 minutes look the same on the dashboard.
# Tunable via the LOG_WINDOW_MINUTES env var.
_LOG_WINDOW_MINUTES: int = int(os.getenv("LOG_WINDOW_MINUTES", "30"))
_LOG_PAGE_SIZE: int = 100    # Render caps /v1/logs at 100 entries per request
_LOG_MAX_PAGES: int = 12     # safety valve: at most 1200 lines per window fetch
_LOG_PAGE_DELAY: float = 0.15  # seconds between paginated calls — avoids burst 429s

# Owner id is required by the /v1/logs endpoint; it never changes, so fetch once.
_OWNER_ID: str | None = None


class RenderChecker:
    """Determines service health from Render logs, with URL fallback if logs are unavailable."""

    def __init__(self):
        self.api_key    = settings.RENDER_API_KEY
        self.service_id = settings.MONITOR_SERVICE_ID
        self.api_url    = settings.RENDER_API_URL
        self.log_window_minutes = _LOG_WINDOW_MINUTES
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
        Fetch every log line from the last _LOG_WINDOW_MINUTES minutes via Render's
        /v1/logs endpoint, paginating as needed. Cached for _LOG_CACHE_TTL seconds.

        Fetching a fixed TIME WINDOW instead of a fixed line count keeps the displayed
        span consistent — a busy period and a quiet period both show the same N minutes,
        rather than the old behaviour where 200 lines could be 5 minutes or over an hour.

        Returns normalized entries, newest first. Empty list on failure.
        """
        global _LOG_CACHE, _LOG_CACHE_TS

        if not force and _LOG_CACHE and (_time.monotonic() - _LOG_CACHE_TS) < _LOG_CACHE_TTL:
            return _LOG_CACHE

        owner = self._get_owner_id()
        if not owner:
            logger.warning("Could not resolve Render ownerId — cannot fetch logs")
            return _LOG_CACHE

        now = datetime.datetime.now(datetime.timezone.utc)
        start_time = (now - datetime.timedelta(minutes=_LOG_WINDOW_MINUTES)).isoformat()
        end_time = now.isoformat()

        collected: list = []
        seen: set = set()
        try:
            for i in range(_LOG_MAX_PAGES):
                if i > 0:
                    _time.sleep(_LOG_PAGE_DELAY)  # spread calls so a burst doesn't trip 429
                r = requests.get(
                    f"{self.api_url}/logs",
                    headers=self.headers,
                    params={
                        "ownerId":   owner,
                        "resource":  self.service_id,
                        "startTime": start_time,
                        "endTime":   end_time,
                        "limit":     _LOG_PAGE_SIZE,
                    },
                    timeout=15,
                )
                if r.status_code == 429:
                    # Rate-limited — keep the last good window rather than erroring out.
                    logger.warning("Render logs API rate-limited (429) — serving cached logs")
                    return _LOG_CACHE or collected
                r.raise_for_status()
                data = r.json()
                page = data.get("logs") or []   # key may be present but null

                for entry in page:
                    norm = self._normalize(entry)
                    # Page boundaries can repeat an entry — dedupe by id (or ts+message).
                    key = norm.get("id") or (norm.get("timestamp"), norm.get("message"))
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(norm)

                # Walk further back within the window (endTime moves toward start_time).
                next_end = data.get("nextEndTime")
                if not data.get("hasMore") or not page or not next_end or next_end == end_time:
                    break
                end_time = next_end

            collected.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
            _LOG_CACHE    = collected
            _LOG_CACHE_TS = _time.monotonic()
            logger.info(f"Fetched {len(collected)} log lines from Render (last {_LOG_WINDOW_MINUTES}m)")
            return collected
        except Exception as e:
            logger.error(f"Failed to fetch Render logs: {e}")
            return _LOG_CACHE   # return stale cache rather than crashing

    def fetch_recent(self, limit: int = _RECENT_LIMIT) -> list:
        """
        Single-call fetch of the newest log lines — cheap, for the health check.
        No pagination and no time window: liveness is decided from the latest activity,
        so one request per check keeps us far under Render's rate limit.
        Returns normalized entries, newest first.
        """
        global _RECENT_CACHE, _RECENT_CACHE_TS

        if _RECENT_CACHE and (_time.monotonic() - _RECENT_CACHE_TS) < _RECENT_CACHE_TTL:
            return _RECENT_CACHE

        owner = self._get_owner_id()
        if not owner:
            logger.warning("Could not resolve Render ownerId — cannot fetch logs")
            return _RECENT_CACHE

        try:
            r = requests.get(
                f"{self.api_url}/logs",
                headers=self.headers,
                params={"ownerId": owner, "resource": self.service_id, "limit": limit},
                timeout=15,
            )
            if r.status_code == 429:
                logger.warning("Render logs API rate-limited (429) — using cached recent logs")
                return _RECENT_CACHE
            r.raise_for_status()
            data = r.json()
            logs = [self._normalize(e) for e in (data.get("logs") or [])]
            logs.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
            _RECENT_CACHE    = logs
            _RECENT_CACHE_TS = _time.monotonic()
            return logs
        except Exception as e:
            logger.error(f"Failed to fetch recent Render logs: {e}")
            return _RECENT_CACHE

    # ── Log analysis ─────────────────────────────────────────────────────────

    _STARTUP_OK = [
        "application startup complete",
        "uvicorn running on",
        "started server process",
        "your service is live",
    ]

    # TRUE process-death signals — the process actually exited or failed to boot.
    # NOTE: a per-request "Exception in ASGI application" / "Traceback" is deliberately
    # NOT here. Those mean a single request handler threw while the server keeps serving —
    # they are not an outage, and treating them as one caused false DOWN alerts that never
    # recovered (the error lingered in the time window).
    _FATAL = [
        "application startup failed",
        "exited with status",
        "exited with code",
        "worker failed to boot",
        "worker failed or couldn't boot",
        "out of memory",
        "ran out of memory",
        "killed",
    ]

    # Markers proving the server is alive and handling traffic (uvicorn access logs).
    _REQUEST_MARKERS = ('"get ', '"post ', '"put ', '"patch ', '"delete ', '"head ', '"options ')

    def _text(self, entry: dict) -> str:
        return (entry.get("message") or "").lower()

    def _is_serving(self, entry: dict) -> bool:
        """True if the line proves the server is alive: a startup banner, an access log, or a keep-alive."""
        t = self._text(entry)
        if any(s in t for s in self._STARTUP_OK):
            return True
        if "http/1." in t and any(m in t for m in self._REQUEST_MARKERS):
            return True
        if "keep-alive" in t:
            return True
        return False

    def analyse_logs(self, logs: list) -> tuple[bool, str, str]:
        """
        Decide whether the service is currently UP from its logs.

        Liveness — not the mere presence of an error — is the source of truth. The service
        is UP as long as the newest activity shows it serving requests or freshly started.
        A genuine outage is a fatal process exit (crash / OOM / boot failure) with NO sign
        of life after it. So a one-off ASGI exception no longer flips the service to DOWN,
        and the status recovers as soon as requests are being served again.
        Returns (is_running, issue_type, detail).
        """
        if not logs:
            return True, IssueType.UNKNOWN.value, "No logs available"

        chrono = list(reversed(logs))   # oldest -> newest

        last_serving = -1
        last_fatal   = -1
        fatal_entry  = None
        for i, e in enumerate(chrono):
            if self._is_serving(e):
                last_serving = i
            if any(p in self._text(e) for p in self._FATAL):
                last_fatal  = i
                fatal_entry = e

        # Genuine outage: the process died (or failed to boot) and nothing served afterwards.
        if last_fatal >= 0 and last_fatal > last_serving:
            t   = self._text(fatal_entry)
            raw = (fatal_entry.get("message") or "")[:150]
            if "out of memory" in t or "ran out of memory" in t or "killed" in t:
                return False, "MEMORY_ERROR", f"OOM / process killed: {raw}"
            if "startup failed" in t or "failed to boot" in t or "couldn't boot" in t:
                return False, "STARTUP_ERROR", f"Startup failed: {raw}"
            return False, "APPLICATION_ERROR", f"Process exited: {raw}"

        # Still serving traffic or recently started — service is up.
        if last_serving >= 0:
            return True, "NONE", "OK - service is serving requests"

        # No fatal exit and no serving signal either — nothing to flag.
        return True, "NONE", "OK - no outage signals in recent logs"

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

        logs = self.fetch_recent()
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
                    f"Render API 404 — MONITOR_SERVICE_ID not found or not owned by this key. "
                    f"service_id='{masked_id}' (len={len(sid)}), api_key={key_set}. "
                    f"If this id looks like the monitor's OWN service, you hit the reserved "
                    f"RENDER_SERVICE_ID collision — use MONITOR_SERVICE_ID instead."
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
