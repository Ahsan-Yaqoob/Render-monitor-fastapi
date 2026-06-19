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

    getStatus()                     { return this.request('/status'); }
    getHistoryByDays(limit, days)   { return this.request(`/history?limit=${limit}&days=${days}`); }
    getDailyHistory(days = 90)      { return this.request(`/history/daily?days=${days}`); }
    getServicesHealth()             { return this.request('/services/health'); }
    getRenderLogs(limit = 2000)     { return this.request(`/render-logs?limit=${limit}`); }
    getErrorLogs(days = 4)          { return this.request(`/logs/errors?days=${days}`); }
    triggerManualCheck()            { return this.request('/monitor/check', { method: 'POST' }); }
    clearLogs()                     { return this.request('/monitor/clear-logs', { method: 'POST' }); }
}

const api = new APIClient();
