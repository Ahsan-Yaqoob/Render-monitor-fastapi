// ── Config ────────────────────────────────────────────────────────────────────
// `group` lists the health API keys to combine into one card.
// If any key in the group is down, the card shows down.
const DEFAULT_SERVICES = [
    // Core
    { id: 'core_api',        name: 'Core API',       desc: 'Main FastAPI backend',                       category: 'Core' },
    // AI Features — the 3 Gemini-powered services share the same health check so they're one card
    { id: 'gemini_services', name: 'Gemini AI',      desc: 'Chatbot, text agents & image search',       category: 'AI Features',
      group: ['ai_features', 'groq_agents', 'ai_image_search'] },
    { id: 'voice_agent',     name: 'Voice Agent',    desc: 'Browser Web Speech API (native)',            category: 'AI Features' },
    // Integrations
    { id: 'ai_maps',         name: 'Google Maps',    desc: 'Route & location search',                   category: 'Integrations' },
    { id: 'file_extractor',  name: 'File Extractor', desc: 'PDF, DOCX & Excel text extraction (local)', category: 'Integrations' },
    { id: 'payment_chatbot', name: 'Supabase',        desc: 'Database health check',                     category: 'Integrations' },
];

class StatusDashboard {
    constructor() {
        this.services   = [];
        this.statusData = {};      // id -> { currentStatus, bars, uptime, records }
        this.isLoading  = false;
        this.tooltip    = null;
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
        document.getElementById('clearLogsBtn')?.addEventListener('click', () => this.clearLogs());
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

            // Per-service health via monitor backend proxy (server-to-server — AI URL never exposed to browser)
            let perServiceHealth = null;
            try {
                const healthRes = await api.getServicesHealth();
                if (healthRes?.success) perServiceHealth = healthRes.data;
            } catch {}

            // Build bars — prefer pre-computed daily data (Supabase), fall back to event-based
            const globalRecords = globalHistory?.data?.records || [];
            let sharedBars;
            try {
                const dailyRes = await api.getDailyHistory(90);
                const dailyRows = dailyRes?.data || [];
                sharedBars = dailyRows.length
                    ? this.buildBarsFromDaily(dailyRows)
                    : this.buildBars(globalRecords, 90);
            } catch {
                sharedBars = this.buildBars(globalRecords, 90);
            }
            const sharedUptime = this.calcUptime(sharedBars);

            for (const s of this.services) {
                // `group` lets multiple health-API keys map to one card.
                const ids = s.group || [s.id];
                let currentStatus = 'unknown';
                let healthDetail  = null;

                if (perServiceHealth) {
                    const anyDown = ids.some(k => perServiceHealth[k]?.status === 'down');
                    const anyUp   = ids.some(k => perServiceHealth[k]?.status === 'up');
                    if (anyDown) {
                        currentStatus = 'down';
                        const downKey = ids.find(k => perServiceHealth[k]?.status === 'down');
                        healthDetail  = perServiceHealth[downKey]?.detail || null;
                    } else if (anyUp) {
                        currentStatus = 'up';
                        const upKey  = ids.find(k => perServiceHealth[k]?.status === 'up');
                        healthDetail  = perServiceHealth[upKey]?.detail || null;
                    }
                }

                if (currentStatus === 'unknown') {
                    if (globalStatus?.data?.is_running === true)  currentStatus = 'up';
                    if (globalStatus?.data?.is_running === false) currentStatus = 'down';
                }

                this.statusData[s.id] = {
                    currentStatus,
                    healthDetail,
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
        const todayStr = new Date().toISOString().slice(0, 10);

        // Monitoring start = earliest event record date, default to today
        let firstDate = todayStr;
        if (records.length > 0) {
            const dates = records.map(r => r.timestamp?.slice(0, 10)).filter(Boolean).sort();
            if (dates.length) firstDate = dates[0];
        }

        // Phase 1 (< 90 days running): fixed window [firstDate … firstDate+89]
        //   → today is somewhere on the left, future days are gray on the right
        // Phase 2 (≥ 90 days running): sliding window [today-89 … today]
        //   → all bars have real data, window advances one day per day
        const start = new Date(firstDate + 'T12:00:00');
        const today = new Date(todayStr    + 'T12:00:00');
        const daysSinceStart = Math.round((today - start) / 86400000);
        const windowStart = daysSinceStart >= days
            ? new Date(today.getTime() - (days - 1) * 86400000)
            : start;

        const dayMap = new Map();
        for (let i = 0; i < days; i++) {
            const d = new Date(windowStart.getTime() + i * 86400000);
            const key = d.toISOString().slice(0, 10);
            dayMap.set(key, {
                date:      key,
                status:    key > todayStr ? 'nodata' : 'up',
                downtime:  0,
                failCount: 0,
            });
        }

        for (const r of records) {
            const key = r.timestamp?.slice(0, 10);
            if (!key || !dayMap.has(key)) continue;
            const day = dayMap.get(key);
            if (day.status === 'nodata') continue;
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

        return [...dayMap.values()];
    }

    buildBarsFromDaily(rows, days = 90) {
        const todayStr = new Date().toISOString().slice(0, 10);
        const rowMap   = new Map(rows.map(r => [r.date, r]));

        // Monitoring start = first DB row date, default to today
        const firstDate = rows.length ? rows[0].date : todayStr;

        // Same two-phase window as buildBars()
        const start = new Date(firstDate + 'T12:00:00');
        const today = new Date(todayStr   + 'T12:00:00');
        const daysSinceStart = Math.round((today - start) / 86400000);
        const windowStart = daysSinceStart >= days
            ? new Date(today.getTime() - (days - 1) * 86400000)
            : start;

        const bars = [];
        for (let i = 0; i < days; i++) {
            const d = new Date(windowStart.getTime() + i * 86400000);
            const key = d.toISOString().slice(0, 10);

            if (key > todayStr) {
                bars.push({ date: key, status: 'nodata', downtime: 0, failCount: 0 });
            } else if (rowMap.has(key)) {
                const r = rowMap.get(key);
                bars.push({ date: key, status: r.status || 'up', downtime: r.downtime_minutes || 0, failCount: r.down_checks || 0 });
            } else {
                bars.push({ date: key, status: 'nodata', downtime: 0, failCount: 0 });
            }
        }
        return bars;
    }

    calcUptime(bars) {
        const monitored = bars.filter(b => b.status !== 'nodata');
        if (!monitored.length) return null;

        // Use actual downtime minutes, not binary up/down per day.
        // A partial outage of 5 min in a day = 99.65% uptime, not 0%.
        const totalMinutes = monitored.length * 24 * 60;
        const downMinutes  = monitored.reduce((sum, b) => {
            if (b.status === 'up') return sum;
            // full day down with no duration data → treat as full day
            if (b.status === 'down')    return sum + (b.downtime > 0 ? b.downtime : 24 * 60);
            // partial outage with no duration data → tiny penalty (won't floor to 0)
            if (b.status === 'partial') return sum + (b.downtime > 0 ? b.downtime : 1);
            return sum;
        }, 0);
        const pct = Math.max(0, ((totalMinutes - downMinutes) / totalMinutes) * 100);
        return pct >= 100 ? '100' : pct.toFixed(2);
    }

    // ── Render ────────────────────────────────────────────────────────────────

    renderOverallBanner(globalStatus, perServiceHealth) {
        const banner = document.getElementById('overallBanner');
        const icon   = document.getElementById('overallIcon');
        const title  = document.getElementById('overallTitle');
        const sub    = document.getElementById('overallSub');
        const dot    = document.getElementById('brandDot');

        // Core service = the actual backend process. If it's down, everything is down.
        const coreDown    = this.statusData['core_api']?.currentStatus === 'down';
        const anyDown     = Object.values(this.statusData).some(d => d?.currentStatus === 'down');
        const isPartial   = anyDown && !coreDown;  // some integrations down but core is up

        const bannerCls   = coreDown ? 'banner-down' : isPartial ? 'banner-warn' : 'banner-ok';
        const iconTxt     = coreDown ? '✗' : isPartial ? '!' : '✓';
        const titleTxt    = coreDown   ? 'Service Outage Detected'
                          : isPartial  ? 'Partial Outage — Some Services Degraded'
                          : 'All Systems Operational';

        if (banner) {
            banner.classList.remove('banner-ok', 'banner-down', 'banner-warn');
            banner.classList.add(bannerCls);
        }
        if (icon)  icon.textContent  = iconTxt;
        if (title) title.textContent = titleTxt;
        if (dot)   coreDown ? dot.classList.add('dot-down') : dot.classList.remove('dot-down');

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

        // Group by category, preserving definition order
        const groups = {};
        for (const s of this.services) {
            const cat = s.category || 'Services';
            (groups[cat] = groups[cat] || []).push(s);
        }

        let html = '';
        for (const [cat, services] of Object.entries(groups)) {
            html += `<div class="service-category-label">${cat}</div>`;
            html += services.map(s => this.buildServiceCard(s)).join('');
        }

        container.innerHTML = html;
        this.attachBarEvents();
    }

    buildServiceCard(service) {
        const id   = service.id;
        const data = this.statusData[id] || { currentStatus: 'unknown', bars: this.buildBars([]), uptime: null, healthDetail: null };
        const { currentStatus, bars, uptime, healthDetail } = data;

        const badgeCls = currentStatus === 'up'   ? 'badge-ok'
                       : currentStatus === 'down' ? 'badge-fail'
                       : 'badge-unknown';
        const badgeTxt = currentStatus === 'up'   ? 'Operational'
                       : currentStatus === 'down' ? 'Outage'
                       : 'Unknown';

        const barsHTML = bars.map(b => {
            const dt  = b.downtime > 0 ? ` · Down ${this.fmtDur(b.downtime)}` : '';
            const lbl = b.status === 'nodata'  ? 'No data'
                      : b.status === 'up'      ? 'No issues'
                      : b.status === 'partial' ? `Partial outage${dt}`
                      : `Outage${dt}`;
            return `<div class="uptime-bar bar-${b.status}" data-date="${b.date}" data-label="${lbl}"></div>`;
        }).join('');

        const todayStr  = new Date().toISOString().slice(0, 10);
        const firstBar  = bars[0];
        const lastBar   = bars[bars.length - 1];
        const fmtDate   = d => new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const leftLabel  = firstBar ? fmtDate(firstBar.date) : 'Today';
        const rightLabel = !lastBar              ? 'Today'
                         : lastBar.date === todayStr ? 'Today'
                         : fmtDate(lastBar.date);

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
            ${healthDetail && healthDetail !== 'OK' ? `<div class="service-detail">${healthDetail}</div>` : ''}
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
            <span>${rightLabel}</span>
        </div>
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

    clearLogs() {
        const btn = document.getElementById('clearLogsBtn');
        if (!btn) return;

        // First click: show inline confirm
        if (btn.dataset.confirming !== 'true') {
            btn.dataset.confirming = 'true';
            btn.textContent = 'Confirm? Click again';
            btn.style.background = 'rgba(239,68,68,0.35)';
            this._clearConfirmTimer = setTimeout(() => {
                btn.dataset.confirming = '';
                btn.textContent = '🗑 Clear Logs';
                btn.style.background = '';
            }, 4000);
            return;
        }

        // Second click: confirmed — do it
        clearTimeout(this._clearConfirmTimer);
        btn.dataset.confirming = '';
        btn.disabled = true;
        btn.textContent = 'Clearing…';
        btn.style.background = '';

        api.clearLogs()
            .then(() => this.loadAll())
            .then(() => this.showAlert('Logs cleared successfully.', 'success'))
            .catch(() => this.showAlert('Failed to clear logs.', 'error'))
            .finally(() => {
                btn.disabled = false;
                btn.textContent = '🗑 Clear Logs';
            });
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
