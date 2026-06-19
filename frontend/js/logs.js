// ── Logs page ───────────────────────────────────────────────────────────────
// Dedicated page for the live Render server logs + an errors list + outage history.
// The viewer structure lives in logs.html and persists, so refreshes update the
// content in place (no flash) and the log tail can stick to the bottom.

class LogsPage {
    constructor() {
        this.logs        = [];    // merged log entries: DB 4-day history + live Render window
        this.win         = null;  // window minutes reported by the backend
        this.err         = null;  // fetch error message, if any
        this.filter      = 'all';
        this.search      = '';
        this.stick       = true;  // follow newest line at the bottom
        this.scroll      = null;
        this.isLoading   = false;
        this._hasDBHistory = false;   // true when DB returned 4-day log history
        this._dbErrorLogs  = null;    // stored error/warn lines from Supabase (30 days), or null
        this._dbErrorDays  = 30;
        this.init();
    }

    init() {
        this.initTheme();
        this.box = document.getElementById('slogBox');
        this.setupEvents();
        this.loadAll();
        setInterval(() => this.loadAll(), 30000);
    }

    // ── Theme ─────────────────────────────────────────────────────────────────

    initTheme() {
        const saved = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', saved);
        this.updateThemeBtn(saved);
    }
    updateThemeBtn(theme) {
        const btn = document.getElementById('themeToggleBtn');
        if (btn) btn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
    toggleTheme() {
        const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        this.updateThemeBtn(next);
    }

    // ── Events ──────────────────────────────────────────────────────────────────

    setupEvents() {
        document.getElementById('themeToggleBtn')?.addEventListener('click', () => this.toggleTheme());
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.loadAll());
        document.getElementById('clearErrorsBtn')?.addEventListener('click', () => this.clearErrors());
        window.addEventListener('visibilitychange', () => { if (!document.hidden) this.loadAll(); });

        document.querySelectorAll('.slog-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                this.filter = chip.dataset.f;
                document.querySelectorAll('.slog-chip').forEach(c => c.classList.toggle('active', c === chip));
                this.stick = true;
                this.renderLogLines();
            });
        });

        const search = document.getElementById('slogSearch');
        search?.addEventListener('input', () => {
            this.search = search.value;
            this.stick = true;
            this.renderLogLines();
        });

        this.box?.addEventListener('scroll', () => {
            this.scroll = this.box.scrollTop;
            this.stick  = (this.box.scrollHeight - this.box.scrollTop - this.box.clientHeight) < 48;
        });
    }

    // ── Data loading ──────────────────────────────────────────────────────────

    async loadAll() {
        if (this.isLoading) return;
        this.isLoading = true;
        try {
            await Promise.all([this.loadLogs(), this.loadErrorLogs(), this.loadOutages()]);
            this.updateRefreshTime();
        } finally {
            this.isLoading = false;
        }
    }

    async loadLogs() {
        // Load DB 4-day history and live Render window in parallel
        const [dbRes, liveRes] = await Promise.allSettled([
            api.getLogHistory(4),
            api.getRenderLogs()
        ]);

        const dbLogs   = (dbRes.status === 'fulfilled'   && dbRes.value?.success)   ? (dbRes.value.data   || []) : [];
        const liveLogs = (liveRes.status === 'fulfilled' && liveRes.value?.success) ? (liveRes.value.data || []) : [];

        this._hasDBHistory = dbLogs.length > 0;
        this.win = liveRes.status === 'fulfilled' ? liveRes.value?.window_minutes : this.win;

        const merged = this._mergeLogs(dbLogs, liveLogs);
        if (merged.length || !this.logs.length) this.logs = merged;

        if (!this.logs.length) {
            this.err = liveRes.status === 'rejected' ? liveRes.reason?.message : null;
        } else {
            this.err = null;
        }

        this.renderLogLines();
        this.renderErrorList(this._dbErrorLogs);
    }

    _mergeLogs(dbLogs, liveLogs) {
        const seen = new Set();
        const out  = [];
        for (const e of [...dbLogs, ...liveLogs]) {
            const key = e.id || `${e.timestamp}:${e.message}`;
            if (!seen.has(key)) { seen.add(key); out.push(e); }
        }
        return out.sort((a, b) => a.timestamp < b.timestamp ? 1 : -1);
    }

    async loadErrorLogs() {
        try {
            const res = await api.getErrorLogs(30);
            if (res?.success) {
                this._dbErrorLogs = res.data || [];
                this._dbErrorDays = res.days || 30;
                this.renderErrorList(this._dbErrorLogs);
                return;
            }
        } catch {}
        // Supabase not configured or empty — fall back to filtering current logs
        this._dbErrorLogs = null;
        this.renderErrorList(null);
    }

    async loadOutages() {
        let records = [];
        try {
            const res = await api.getHistoryByDays(2000, 90);
            records = res?.data?.records || [];
        } catch {}
        this.renderOutageHistory(records);
    }

    // ── Log classification ──────────────────────────────────────────────────────

    classify(e) {
        const lvl = (e.level || '').toLowerCase();
        const ml  = (e.message || '').toLowerCase();
        if (lvl === 'error' || lvl === 'critical' ||
            /traceback|exception|\bkilled\b|out of memory|exited with|startup failed/.test(ml)) return 'error';
        const m = ml.match(/http\/1\.\d"?\s+(\d{3})/);
        if (m) { const c = +m[1]; if (c >= 500) return 'error'; if (c >= 400) return 'warn'; }
        if (lvl === 'warning' || lvl === 'warn' || /\bwarn(ing)?\b/.test(ml)) return 'warn';
        if (/application startup complete|uvicorn running|started server|your service is live/.test(ml)) return 'ok';
        return 'info';
    }

    isRequestLine(e) {
        return /"(get|post|put|patch|delete|head|options)\b.*http\/1\./i.test(e.message || '');
    }

    // ── Live log viewer ─────────────────────────────────────────────────────────

    renderLogLines() {
        const box   = this.box;
        const sub   = document.getElementById('slogSub');
        const dot   = document.getElementById('slogDot');
        const stats = document.getElementById('slogStats');
        if (!box) return;

        if (this.err) {
            box.innerHTML = `<div class="rlog-placeholder">Could not load logs: ${this.esc(this.err)}</div>`;
            if (dot)   dot.className = 'srv-logs-dot warn';
            if (stats) stats.innerHTML = '';
            return;
        }
        if (sub) sub.textContent = this._hasDBHistory
            ? `Render · last 4 days`
            : `Render${this.win ? ' · last ' + this.win + ' min' : ''}`;
        if (!this.logs.length) {
            box.innerHTML = `<div class="rlog-placeholder">No logs returned from Render.</div>`;
            if (stats) stats.innerHTML = '';
            return;
        }

        const cls  = this.logs.map(e => this.classify(e));
        const errN = cls.filter(c => c === 'error').length;
        const warN = cls.filter(c => c === 'warn').length;

        if (dot)   dot.className = 'srv-logs-dot ' + (errN ? 'err' : 'ok');
        if (stats) stats.innerHTML =
            `<span class="slog-stat">${this.logs.length} lines</span>` +
            (errN ? `<span class="slog-stat err">${errN} error${errN > 1 ? 's' : ''}</span>` : '') +
            (warN ? `<span class="slog-stat warn">${warN} warning${warN > 1 ? 's' : ''}</span>` : '');

        const f = this.filter;
        const q = (this.search || '').trim().toLowerCase();
        let rows = this.logs.map((e, i) => ({ e, c: cls[i] }));
        if (f === 'error')        rows = rows.filter(r => r.c === 'error');
        else if (f === 'warn')    rows = rows.filter(r => r.c === 'warn');
        else if (f === 'request') rows = rows.filter(r => this.isRequestLine(r.e));
        if (q) rows = rows.filter(r => (r.e.message || '').toLowerCase().includes(q));

        if (!rows.length) {
            box.innerHTML = `<div class="rlog-placeholder">No log lines match this filter.</div>`;
            return;
        }

        // Chronological: oldest at top, newest at the bottom (logs arrive newest-first)
        rows.reverse();
        box.innerHTML = rows.map(({ e, c }) => this.logLineHTML(e, c)).join('');

        if (this.stick) box.scrollTop = box.scrollHeight;
        else if (this.scroll != null) box.scrollTop = this.scroll;
    }

    logLineHTML(e, c) {
        const BADGE = { error: 'ERR', warn: 'WARN', ok: 'OK', info: 'INFO' };
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '';
        return `<div class="rlog-line rlog-${c}">`
             +    `<span class="rlog-ts">${ts}</span>`
             +    `<span class="rlog-badge rlog-badge-${c}">${BADGE[c]}</span>`
             +    `<span class="rlog-msg">${this.fmtMsg(e.message || '')}</span>`
             +  `</div>`;
    }

    // ── Errors & warnings list — grouped by date, collapsible ───────────────────

    renderErrorList(dbRows) {
        const list  = document.getElementById('errorList');
        const count = document.getElementById('errCount');
        const dot   = document.getElementById('errDot');
        if (!list) return;

        let errors;
        let windowLabel;

        if (dbRows && dbRows.length) {
            errors      = dbRows.map(e => ({ e, c: this.classify(e) }));
            windowLabel = `${this._dbErrorDays} days`;
        } else if (!dbRows) {
            errors      = this.logs.map(e => ({ e, c: this.classify(e) })).filter(r => r.c === 'error' || r.c === 'warn');
            windowLabel = `${this.win || 30} minutes`;
        } else {
            errors      = [];
            windowLabel = `${this._dbErrorDays} days`;
        }

        if (dot)   dot.className = 'srv-logs-dot ' + (errors.some(r => r.c === 'error') ? 'err' : errors.length ? 'warn' : 'ok');
        if (count) count.textContent = errors.length ? `${errors.length}` : '';

        if (!errors.length) {
            list.innerHTML = `<div class="error-empty">✓ No errors or warnings in the last ${windowLabel}.</div>`;
            return;
        }

        // Group by date label
        const today = new Date();
        const todayStr = today.toDateString();
        const yest    = new Date(today); yest.setDate(today.getDate() - 1);
        const yestStr = yest.toDateString();

        const groups = new Map();   // label → [{e, c}]
        for (const row of errors.slice(0, 500)) {
            const d  = row.e.timestamp ? new Date(row.e.timestamp) : new Date();
            const ds = d.toDateString();
            const label = ds === todayStr ? 'Today'
                        : ds === yestStr  ? 'Yesterday'
                        : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
            if (!groups.has(label)) groups.set(label, []);
            groups.get(label).push(row);
        }

        list.innerHTML = [...groups.entries()].map(([label, rows], idx) => {
            const errN = rows.filter(r => r.c === 'error').length;
            const warN = rows.filter(r => r.c === 'warn').length;
            const badge = [
                errN ? `${errN} error${errN > 1 ? 's' : ''}` : '',
                warN ? `${warN} warning${warN > 1 ? 's' : ''}` : '',
            ].filter(Boolean).join(' · ');

            const items = rows.map(({ e, c }) => {
                const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '';
                return `<div class="error-item error-${c}">`
                     +   `<span class="rlog-badge rlog-badge-${c}">${c === 'error' ? 'ERR' : 'WARN'}</span>`
                     +   `<div class="error-body">`
                     +     `<div class="error-msg">${this.fmtMsg(e.message || '')}</div>`
                     +     `<div class="error-time">${ts}</div>`
                     +   `</div>`
                     + `</div>`;
            }).join('');

            return `<details class="err-group" ${idx === 0 ? 'open' : ''}>`
                 +   `<summary class="err-group-header">`
                 +     `<span class="err-group-arrow">▶</span>`
                 +     `<span class="err-group-label">${label}</span>`
                 +     `<span class="err-group-badge">${badge}</span>`
                 +   `</summary>`
                 +   `<div class="err-group-items">${items}</div>`
                 + `</details>`;
        }).join('');
    }

    async clearErrors() {
        const btn = document.getElementById('clearErrorsBtn');
        if (btn) btn.disabled = true;
        try {
            await api.clearErrorLogs();
            this._dbErrorLogs = [];
            this.renderErrorList([]);
        } catch (e) {
            console.error('Failed to clear errors:', e);
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // ── Outage history (FAILED / RECOVERED events) ───────────────────────────────

    renderOutageHistory(records) {
        const list  = document.getElementById('outageList');
        const count = document.getElementById('outageCount');
        if (!list) return;

        const events = [...records].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
        if (count) count.textContent = events.length ? `${events.length}` : '';

        if (!events.length) {
            list.innerHTML = `<div class="error-empty">✓ No outages recorded — the service has been healthy.</div>`;
            return;
        }

        list.innerHTML = events.slice(0, 100).map(r => {
            const isFail = r.status === 'FAILED';
            const date   = new Date(r.timestamp).toLocaleString();
            const issue  = (r.issue_type && r.issue_type !== 'NONE') ? r.issue_type : '';
            const dur    = (!isFail && r.duration > 0) ? `Down for ${this.fmtDur(r.duration)}` : '';
            return `<div class="outage-item">`
                 +    `<span class="badge ${isFail ? 'badge-fail' : 'badge-ok'}">`
                 +        `<span class="badge-dot"></span>${isFail ? 'FAILED' : 'RECOVERED'}</span>`
                 +    `<div class="outage-body">`
                 +        `<div class="outage-date">${date}</div>`
                 +        `<div class="outage-meta">${[issue, dur].filter(Boolean).join(' · ')}</div>`
                 +    `</div>`
                 +  `</div>`;
        }).join('');
    }

    // ── Helpers ─────────────────────────────────────────────────────────────────

    fmtMsg(msg) {
        let s = this.esc(msg);
        s = s.replace(/\[([A-Za-z0-9_\-]{2,24})\]/g, '<span class="rlog-tag">[$1]</span>');
        s = s.replace(/(HTTP\/1\.\d"?\s+)(\d{3})/g, (_, pre, code) => {
            const c = +code;
            const sc = c >= 500 ? 'sc-err' : c >= 400 ? 'sc-warn' : (c >= 200 && c < 300) ? 'sc-ok' : 'sc-info';
            return pre + `<span class="rlog-status ${sc}">${code}</span>`;
        });
        return s;
    }

    esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    fmtDur(minutes) {
        if (!minutes || minutes < 1) return '< 1m';
        const h = Math.floor(minutes / 60);
        const m = Math.floor(minutes % 60);
        if (h === 0) return `${m}m`;
        if (m === 0) return `${h}h`;
        return `${h}h ${m}m`;
    }

    updateRefreshTime() {
        const el = document.getElementById('refreshTime');
        if (el) el.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
}

document.addEventListener('DOMContentLoaded', () => new LogsPage());
