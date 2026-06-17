class APIClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.timeout = 10000;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), this.timeout);
        try {
            const res = await fetch(url, {
                method: options.method || 'GET',
                headers: { 'Content-Type': 'application/json', ...options.headers },
                signal: controller.signal,
                ...options,
            });
            clearTimeout(tid);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error || `HTTP ${res.status}`);
            }
            return await res.json();
        } catch (e) {
            clearTimeout(tid);
            if (e.name === 'AbortError') throw new Error('Request timeout');
            throw e;
        }
    }

    // ── Single-service endpoints (existing backend) ────────────────────────────

    getStatus()                     { return this.request('/status'); }
    getHistory(limit = 100)         { return this.request(`/history?limit=${limit}`); }
    getHistoryByDays(limit, days)   { return this.request(`/history?limit=${limit}&days=${days}`); }
    getStats(days = 30)             { return this.request(`/stats?days=${days}`); }
    triggerManualCheck()            { return this.request('/monitor/check', { method: 'POST' }); }
    clearLogs()                     { return this.request('/monitor/clear-logs', { method: 'POST' }); }

    // ── Multi-service endpoints (added once backend is updated) ───────────────

    getServices()                   { return this.request('/services'); }
    getServiceStatus(id)            { return this.request(`/services/${id}/status`); }
    getServiceHistory(id, days=90)  { return this.request(`/services/${id}/history?days=${days}`); }
    getServiceLogs(id, limit=50)    { return this.request(`/services/${id}/logs?limit=${limit}`); }
}

const api = new APIClient();
