class DashboardCharts {
    constructor() {
        this.charts = {};
    }

    isDark() {
        return document.documentElement.getAttribute('data-theme') !== 'light';
    }

    colors() {
        const dark = this.isDark();
        return {
            grid:  dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)',
            tick:  dark ? '#475569' : '#94a3b8',
            label: dark ? '#94a3b8' : '#64748b',
        };
    }

    baseOptions(c) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: this.isDark() ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.95)',
                    titleColor: this.isDark() ? '#e2e8f0' : '#0f172a',
                    bodyColor:  this.isDark() ? '#94a3b8' : '#475569',
                    borderColor: this.isDark() ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 10,
                },
            },
            scales: {
                x: {
                    grid: { color: c.grid, drawBorder: false },
                    ticks: { color: c.tick, font: { size: 11 }, maxRotation: 30 },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: c.grid, drawBorder: false },
                    ticks: { color: c.tick, font: { size: 11 }, stepSize: 1 },
                },
            },
        };
    }

    async loadIssueChart() {
        try {
            const res = await api.getIssueFrequency();
            const ctx = document.getElementById('issueChart');
            if (!ctx) return;

            this.destroy('issueChart');

            if (!res.success || !Object.keys(res.data).length) {
                this.placeholder(ctx, 'No issue data yet');
                return;
            }

            const c = this.colors();
            this.charts.issueChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: Object.keys(res.data),
                    datasets: [{
                        label: 'Count',
                        data: Object.values(res.data),
                        backgroundColor: 'rgba(239,68,68,0.25)',
                        borderColor: '#ef4444',
                        borderWidth: 1.5,
                        borderRadius: 6,
                        borderSkipped: false,
                    }],
                },
                options: this.baseOptions(c),
            });
        } catch (err) {
            console.error('Issue chart error:', err);
        }
    }

    async loadFailuresChart() {
        try {
            const res = await api.getDailyFailures(30);
            const ctx = document.getElementById('failuresChart');
            if (!ctx) return;

            this.destroy('failuresChart');

            if (!res.success || !Object.keys(res.data).length) {
                this.placeholder(ctx, 'No failure data yet');
                return;
            }

            const c = this.colors();
            this.charts.failuresChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Object.keys(res.data),
                    datasets: [{
                        label: 'Failures',
                        data: Object.values(res.data),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,0.08)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#2563eb',
                        pointBorderColor: this.isDark() ? '#07090f' : '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    }],
                },
                options: this.baseOptions(c),
            });
        } catch (err) {
            console.error('Failures chart error:', err);
        }
    }

    destroy(id) {
        if (this.charts[id]) {
            this.charts[id].destroy();
            delete this.charts[id];
        }
    }

    placeholder(ctx, msg) {
        const parent = ctx.parentElement;
        if (parent) {
            parent.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:13px;">${msg}</div>`;
        }
    }

    async refreshCharts() {
        await Promise.all([this.loadIssueChart(), this.loadFailuresChart()]);
    }
}

const charts = new DashboardCharts();
