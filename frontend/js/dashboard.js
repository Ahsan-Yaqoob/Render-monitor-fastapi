// ── Config ────────────────────────────────────────────────────────────────────
// Resolved at runtime from /api/status → data.ai_backend_url (set via AI_BACKEND_URL in .env)
let AI_HEALTH_URL = null;

// Service definitions — IDs must match keys returned by /api/health/services
const DEFAULT_SERVICES = [
    // Core
    { id: 'core_api',        name: 'Core API',           desc: 'Main FastAPI backend — health & primary endpoints',  category: 'Core' },
    // AI Features
    { id: 'voice_agent',     name: 'Voice Agent',         desc: 'ElevenLabs speech-to-text WebSocket',                category: 'AI Features' },
    { id: 'ai_features',     name: 'AI Features',         desc: 'Quotation chatbot, analyzer & creator (Gemini)',     category: 'AI Features' },
    { id: 'groq_agents',     name: 'Groq Text Agents',    desc: 'Groq-powered text completion agents',                category: 'AI Features' },
    // Integrations
    { id: 'ai_maps',         name: 'AI Maps',             desc: 'Google Maps route & location search',                category: 'Integrations' },
    { id: 'ai_image_search', name: 'AI Image Search',     desc: 'AI-powered image discovery',                         category: 'Integrations' },
    { id: 'file_extractor',  name: 'File Extractor',      desc: 'PDF, DOCX & Excel text extraction (local)',          category: 'Integrations' },
    { id: 'payment_chatbot', name: 'Payment Chatbot',     desc: 'Make & receive payment agents (Supabase)',           category: 'Integrations' },
];

class StatusDashboard {
    constructor() {
        this.services     = [];
        this.statusData   = {};      // id -> { currentStatus, bars, uptime, records }
        this.expandedLogs = new Set();
        this.isLoading    = false;
        this.tooltip      = null;
        this.init();
    }

    async init() {
        this.initTheme();
        this.tooltip = document.getElementById('barTooltip');
        this.setupHeaderEvents();
        await this.loadAll();
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

    // ── Header events ─────────────────────────────────────────────────────────

    setupHeaderEvents() {
        document.getElementById('themeToggleBtn')?.addEventListener('click', () => this.toggleTheme());
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.loadAll());
        document.getElementById('manualCheckBtn')?.addEventListener('click', () => this.triggerCheck());
        window.addEventListener('visibilitychange', () => { if (!document.hidden) this.loadAll(); });
    }

    // ── Tooltip ───────────────────────────────────────────────────────────────

    showTooltip(e, html) {
        if (!this.tooltip) return;
        this.tooltip.innerHTML = html;
        this.tooltip.classList.add('visible');
        this.placeTooltip(e);
    }

    hideTooltip() { this.tooltip?.classList.remove('visible'); }

    placeTooltip(e) {
        if (!this.tooltip) return;
        const tw = this.tooltip.offsetWidth || 160;
        const th = this.tooltip.offsetHeight || 40;
        let x = e.clientX - tw / 2;
        let y = e.clientY - th - 14;
        x = Math.max(8, Math.min(x, window.innerWidth - tw - 8));
        if (y < 8) y = e.clientY + 14;
        this.tooltip.style.left = x + 'px';
        this.tooltip.style.top  = y + 'px';
    }

    // ── Data loading ──────────────────────────────────────────────────────────

    async loadAll() {
        if (this.isLoading) return;
        this.isLoading = true;
        try {
            this.services = DEFAULT_SERVICES;

            // Fetch Render Monitor backend data (history + overall status)
            let globalHistory = null;
            let globalStatus  = null;
            try { globalHistory = await api.getHistoryByDays(2000, 90); } catch {}
            try { globalStatus  = await api.getStatus();                } catch {}

            // Resolve AI backend health URL from status response (set via AI_BACKEND_URL in .env)
            if (!AI_HEALTH_URL && globalStatus?.data?.ai_backend_url) {
                AI_HEALTH_URL = globalStatus.data.ai_backend_url.replace(/\/$/, '') + '/api/health/services';
            }

            // Fetch per-service live health from AI backend directly
            let perServiceHealth = null;
            if (AI_HEALTH_URL) {
                try {
                    const ctrl = new AbortController();
                    const tid  = setTimeout(() => ctrl.abort(), 8000);
                    const res  = await fetch(AI_HEALTH_URL, { signal: ctrl.signal });
                    clearTimeout(tid);
                    if (res.ok) {
                        const json = await res.json();
                        if (json.success) perServiceHealth = json.data;
                    }
                } catch {}
            }

            // Build bars from global history (all services share same backend)
            const globalRecords = globalHistory?.data?.records || [];
            const sharedBars    = this.buildBars(globalRecords, 90);
            const sharedUptime  = this.calcUptime(sharedBars);

            // Load per-service current status
            for (const s of this.services) {
                const id = s.id;

                // Current status: from per-service health check first
                let currentStatus = 'unknown';
                if (perServiceHealth && id in perServiceHealth) {
                    currentStatus = perServiceHealth[id].status === 'up' ? 'up' : 'down';
                } else if (globalStatus?.data?.is_running === true)  {
                    currentStatus = 'up';
                } else if (globalStatus?.data?.is_running === false) {
                    currentStatus = 'down';
                }

                // History bars: shared (all services on same backend)
                this.statusData[id] = {
                    currentStatus,
                    bars:    sharedBars,
                    uptime:  sharedUptime,
                    records: globalRecords,
                };
            }

            this.renderOverallBanner(globalStatus, perServiceHealth);
            this.renderServices();
            this.updateRefreshTime();
        } catch (err) {
            console.error('Load error:', err);
            this.showAlert('Failed to load status data.', 'error');
        } finally {
            this.isLoading = false;
        }
    }

    // ── Bar data ──────────────────────────────────────────────────────────────

    buildBars(records, days = 90) {
        const now = new Date();
        const dayMap = new Map();

        // Earliest record = monitoring start date
        let monitorStart = null;
        if (records.length > 0) {
            const dates = records.map(r => r.timestamp?.slice(0, 10)).filter(Boolean).sort();
            if (dates.length) monitorStart = dates[0];
        }

        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            const key = d.toISOString().slice(0, 10);
            dayMap.set(key, {
                date:      key,
                status:    (monitorStart && key < monitorStart) ? 'nodata' : 'up',
                downtime:  0,
                failCount: 0,
            });
        }

        for (const r of records) {
            const key = r.timestamp?.slice(0, 10);
            if (!key || !dayMap.has(key)) continue;
            const day = dayMap.get(key);
            if (r.status === 'FAILED') {
                day.failCount++;
                day.downtime += r.duration || 0;
            }
        }

        for (const day of dayMap.values()) {
            if (day.status === 'nodata') continue;
            if (day.failCount > 0) {
                day.status = day.downtime >= 60 ? 'down' : 'partial';
            }
        }

        const allBars = [...dayMap.values()];

        // Only show bars from monitoring start — bars grow day by day from today
        const firstMonitored = allBars.findIndex(b => b.status !== 'nodata');
        if (firstMonitored > 0) return allBars.slice(firstMonitored);
        if (firstMonitored === -1) return allBars.slice(-1); // no data yet: just today
        return allBars;
    }

    calcUptime(bars) {
        const monitored = bars.filter(b => b.status !== 'nodata');
        if (!monitored.length) return null;
        const up  = monitored.filter(b => b.status === 'up').length;
        const pct = (up / monitored.length) * 100;
        return pct >= 100 ? '100' : pct.toFixed(2);
    }

    // ── Render ────────────────────────────────────────────────────────────────

    renderOverallBanner(globalStatus, perServiceHealth) {
        const banner = document.getElementById('overallBanner');
        const icon   = document.getElementById('overallIcon');
        const title  = document.getElementById('overallTitle');
        const sub    = document.getElementById('overallSub');
        const dot    = document.getElementById('brandDot');

        const anyDown = Object.values(this.statusData).some(d => d?.currentStatus === 'down');

        if (banner) {
            banner.classList.remove('banner-ok', 'banner-down', 'banner-warn');
            banner.classList.add(anyDown ? 'banner-down' : 'banner-ok');
        }
        if (icon)  icon.textContent  = anyDown ? '✗' : '✓';
        if (title) title.textContent = anyDown ? 'Service Outage Detected' : 'All Systems Operational';
        if (dot)   anyDown ? dot.classList.add('dot-down') : dot.classList.remove('dot-down');

        if (sub) {
            const lastCheck = globalStatus?.data?.last_check_time;
            if (lastCheck) {
                const ago = Math.round((Date.now() - new Date(lastCheck).getTime()) / 60000);
                sub.textContent = ago < 2 ? 'Checked just now' : `Last checked ${ago} minute${ago !== 1 ? 's' : ''} ago`;
            } else {
                sub.textContent = 'Monitoring active';
            }
        }
    }

    renderServices() {
        const container = document.getElementById('servicesList');
        if (!container) return;

        if (!this.services.length) {
            container.innerHTML = '<div class="empty-state">No services configured.</div>';
            return;
        }

        // Group by category
        const groups = {};
        for (const s of this.services) {
            const cat = s.category || 'Services';
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(s);
        }

        let html = '';
        for (const [cat, services] of Object.entries(groups)) {
            html += `<div class="service-category-label">${cat}</div>`;
            html += services.map(s => this.buildServiceCard(s)).join('');
        }

        container.innerHTML = html;
        this.attachBarEvents();

        // Re-open expanded log panels
        for (const id of this.expandedLogs) {
            const panel = document.getElementById(`logs-${id}`);
            if (panel) {
                panel.style.display = 'block';
                const arrow = document.getElementById(`arrow-${id}`);
                if (arrow) arrow.textContent = '▴';
                this.renderLogPanel(id);
            }
        }
    }

    buildServiceCard(service) {
        const id   = service.id;
        const data = this.statusData[id] || { currentStatus: 'unknown', bars: this.buildBars([]), uptime: null, records: [] };
        const { currentStatus, bars, uptime } = data;

        const badgeCls = currentStatus === 'up'   ? 'badge-ok'
                       : currentStatus === 'down'  ? 'badge-fail'
                       : 'badge-unknown';
        const badgeTxt = currentStatus === 'up'   ? 'Operational'
                       : currentStatus === 'down'  ? 'Outage'
                       : 'Unknown';

        const barsHTML = bars.map(b => {
            const dt  = b.downtime > 0 ? ` · Down ${this.fmtDur(b.downtime)}` : '';
            const lbl = b.status === 'nodata'  ? 'No data'
                      : b.status === 'up'      ? 'No issues'
                      : b.status === 'partial' ? `Partial outage${dt}`
                      : `Outage${dt}`;
            return `<div class="uptime-bar bar-${b.status}" data-date="${b.date}" data-label="${lbl}"></div>`;
        }).join('');

        // Left label: monitoring start date (first bar)
        const firstBar = bars[0];
        const leftLabel = firstBar
            ? new Date(firstBar.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            : 'Today';

        const monitoredDays = bars.filter(b => b.status !== 'nodata').length;
        const uptimeTxt = uptime !== null
            ? `${uptime}% uptime · ${monitoredDays} day${monitoredDays !== 1 ? 's' : ''}`
            : '—';

        return `
<div class="service-card" id="sc-${id}">
    <div class="service-row-header">
        <div class="service-info">
            <div class="service-name">${service.name}</div>
            ${service.desc ? `<div class="service-desc">${service.desc}</div>` : ''}
        </div>
        <span class="badge ${badgeCls}">
            <span class="badge-dot"></span>${badgeTxt}
        </span>
    </div>

    <div class="uptime-wrap">
        <div class="uptime-bars" data-service="${id}">${barsHTML}</div>
        <div class="uptime-labels">
            <span>${leftLabel}</span>
            <span class="uptime-pct">${uptimeTxt}</span>
            <span>Today</span>
        </div>
    </div>

    <div class="view-logs-row">
        <button class="view-logs-btn" id="logbtn-${id}" onclick="dashboard.toggleLogs('${id}')">
            View Logs <span class="log-arrow" id="arrow-${id}">▾</span>
        </button>
    </div>

    <div class="service-log-panel" id="logs-${id}" style="display:none">
        <div class="log-loading">Loading…</div>
    </div>
</div>`;
    }

    attachBarEvents() {
        document.querySelectorAll('.uptime-bar').forEach(bar => {
            bar.addEventListener('mouseenter', e => {
                const rawDate = bar.dataset.date;
                const label   = bar.dataset.label || '';
                let dateStr   = rawDate || '';
                if (rawDate) {
                    try {
                        dateStr = new Date(rawDate + 'T12:00:00').toLocaleDateString('en-US', {
                            month: 'short', day: 'numeric', year: 'numeric',
                        });
                    } catch {}
                }
                this.showTooltip(e, `<strong>${dateStr}</strong>${label ? '<br>' + label : ''}`);
            });
            bar.addEventListener('mousemove', e => this.placeTooltip(e));
            bar.addEventListener('mouseleave', () => this.hideTooltip());
        });
    }

    // ── Log panel ─────────────────────────────────────────────────────────────

    toggleLogs(serviceId) {
        const panel = document.getElementById(`logs-${serviceId}`);
        const arrow = document.getElementById(`arrow-${serviceId}`);
        if (!panel) return;

        const isOpen = panel.style.display !== 'none';
        if (isOpen) {
            panel.style.display = 'none';
            if (arrow) arrow.textContent = '▾';
            this.expandedLogs.delete(serviceId);
        } else {
            panel.style.display = 'block';
            if (arrow) arrow.textContent = '▴';
            this.expandedLogs.add(serviceId);
            this.renderLogPanel(serviceId);
        }
    }

    renderLogPanel(serviceId) {
        const panel = document.getElementById(`logs-${serviceId}`);
        if (!panel) return;

        const data    = this.statusData[serviceId];
        const records = [...(data?.records || [])].reverse();

        if (!records.length) {
            panel.innerHTML = '<div class="log-empty">No events recorded yet — logs will appear here as the backend goes down or recovers.</div>';
            return;
        }

        const items = records.slice(0, 50).map(r => {
            const isFail = r.status === 'FAILED';
            const date   = new Date(r.timestamp).toLocaleString();
            const dur    = (!isFail && r.duration > 0) ? ` · Down for ${this.fmtDur(r.duration)}` : '';
            const issue  = (r.issue_type && r.issue_type !== 'NONE') ? r.issue_type : '';

            return `
<div class="log-event ${isFail ? 'log-fail' : 'log-ok'}">
    <div class="log-dot"></div>
    <div class="log-body">
        <span class="${isFail ? 'lbadge-fail' : 'lbadge-ok'}">${isFail ? 'FAILED' : 'RECOVERED'}</span>
        <span class="log-date">${date}</span>
        ${issue ? `<span class="log-issue">${issue}</span>` : ''}
        ${dur    ? `<span class="log-dur">${dur}</span>`    : ''}
    </div>
</div>`;
        }).join('');

        panel.innerHTML = `<div class="log-list">${items}</div>`;
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    async triggerCheck() {
        const btn = document.getElementById('manualCheckBtn');
        if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }
        try {
            await api.triggerManualCheck();
            await new Promise(r => setTimeout(r, 1200));
            await this.loadAll();
            this.showAlert('Manual check completed.', 'success');
        } catch {
            this.showAlert('Manual check failed.', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '⬡ Check Now'; }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    updateRefreshTime() {
        const el = document.getElementById('refreshTime');
        if (el) el.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }

    showAlert(msg, type = 'success') {
        const c = document.getElementById('alertContainer');
        if (!c) return;
        const d = document.createElement('div');
        d.className = `alert alert-${type}`;
        d.textContent = msg;
        c.appendChild(d);
        setTimeout(() => d.remove(), type === 'error' ? 5000 : 3000);
    }

    fmtDur(minutes) {
        if (!minutes || minutes < 1) return '< 1m';
        const h = Math.floor(minutes / 60);
        const m = Math.floor(minutes % 60);
        if (h === 0) return `${m}m`;
        if (m === 0) return `${h}h`;
        return `${h}h ${m}m`;
    }
}

let dashboard;
document.addEventListener('DOMContentLoaded', () => { dashboard = new StatusDashboard(); });
