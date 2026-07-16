/* Analytics charts. Colors are never hard-coded here: every series reads the
   design tokens in app.css, so a token change (or a theme switch — see the
   mt:themechange listener at the bottom) restyles the charts too. */
(function () {
    'use strict';

    var dataEl = document.getElementById('analytics-data');
    if (!dataEl || typeof Chart === 'undefined') return;
    var data = JSON.parse(dataEl.textContent);
    var charts = [];

    function token(name, fallback) {
        var value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return value || fallback;
    }

    function gbp(value, decimals) {
        return '£' + Number(value).toLocaleString('en-GB', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    // "Jul 2026" -> "Jul"; January keeps the year ("Jan 26") to mark it.
    function shortMonth(label) {
        return label.indexOf('Jan') === 0 ? 'Jan ' + label.slice(-2) : label.slice(0, 3);
    }

    // Everything token-derived lives inside buildCharts so a rebuild after a
    // theme switch re-reads the current values.
    function buildCharts() {
        var accent = token('--mt-chart-accent', '#444ce7');
        var neutral = token('--mt-chart-neutral', '#667085');
        var neutralDeep = token('--mt-chart-neutral-deep', '#667085');
        var neutralSoft = token('--mt-chart-neutral-soft', '#98a2b3');
        var gray500 = token('--mt-gray-500', '#667085');
        var gray700 = token('--mt-gray-700', '#344054');
        var grid = token('--mt-gray-200', '#e4e7ec');
        var surface = token('--mt-surface', '#ffffff');

        // Same tokens as the status/priority badges (design-system rule).
        var statusColors = {
            'Pending': neutral,
            'Scheduled': token('--mt-purple-600', '#6938ef'),
            'In Progress': token('--mt-info-600', '#1570ef'),
            'Completed': token('--mt-success-600', '#079455'),
            'Cancelled': neutralSoft
        };
        var priorityColors = {
            'Low': neutralDeep,
            'Medium': token('--mt-info-600', '#1570ef'),
            'High': token('--mt-warning-600', '#dc6803'),
            'Urgent': token('--mt-danger-600', '#d92d20')
        };

        Chart.defaults.font.family = token('--mt-font', 'Inter, sans-serif');
        Chart.defaults.font.size = 12;
        Chart.defaults.color = gray500;

        // Value at the tip of each horizontal bar, in ink (never the series color).
        var barValueLabels = {
            id: 'barValueLabels',
            afterDatasetsDraw: function (chart) {
                var meta = chart.getDatasetMeta(0);
                var ctx = chart.ctx;
                ctx.save();
                ctx.fillStyle = gray700;
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                meta.data.forEach(function (bar, i) {
                    var value = chart.data.datasets[0].data[i];
                    ctx.fillText(String(value), bar.x + 8, bar.y);
                });
                ctx.restore();
            }
        };

        var hairline = { color: grid, drawTicks: false };

        function countAxis() {
            return { beginAtZero: true, grid: hairline, border: { display: false }, ticks: { precision: 0 } };
        }

        function volumeChart() {
            charts.push(new Chart(document.getElementById('chart-volume'), {
                type: 'bar',
                data: {
                    labels: data.volume.map(function (r) { return r.label; }),
                    datasets: [{
                        // Single series -> one hue, no legend (title carries the name).
                        data: data.volume.map(function (r) { return r.count; }),
                        backgroundColor: accent,
                        maxBarThickness: 24,
                        borderRadius: 4,
                        borderSkipped: 'start'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: function (ctx) { return ctx.parsed.y + (ctx.parsed.y === 1 ? ' job' : ' jobs'); } } }
                    },
                    scales: {
                        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, callback: function (v, i) { return shortMonth(this.getLabelForValue(i)); } } },
                        y: countAxis()
                    }
                }
            }));
        }

        function costLine(label, key, color) {
            return {
                label: label,
                data: data.costs.map(function (r) { return r[key]; }),
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2,
                pointRadius: 4,
                pointBorderColor: surface,
                pointBorderWidth: 2,
                pointHoverRadius: 6
            };
        }

        function costsChart() {
            charts.push(new Chart(document.getElementById('chart-costs'), {
                type: 'line',
                data: {
                    labels: data.costs.map(function (r) { return r.label; }),
                    datasets: [
                        // Actual spend is the story (accent); estimated is context (gray).
                        costLine('Actual', 'actual', accent),
                        costLine('Estimated', 'estimated', neutral)
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, boxHeight: 2, color: gray700 } },
                        tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ': ' + gbp(ctx.parsed.y, 2); } } }
                    },
                    scales: {
                        x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, callback: function (v, i) { return shortMonth(this.getLabelForValue(i)); } } },
                        y: { beginAtZero: true, grid: hairline, border: { display: false }, ticks: { callback: function (v) { return gbp(v, 0); } } }
                    }
                }
            }));
        }

        function breakdownChart(canvasId, rows, labelKey, colorMap, tooltip) {
            charts.push(new Chart(document.getElementById(canvasId), {
                type: 'bar',
                data: {
                    labels: rows.map(function (r) { return r[labelKey]; }),
                    datasets: [{
                        data: rows.map(function (r) { return r.count; }),
                        backgroundColor: colorMap ? rows.map(function (r) { return colorMap[r[labelKey]] || neutral; }) : accent,
                        maxBarThickness: 24,
                        borderRadius: 4,
                        borderSkipped: 'start'
                    }]
                },
                plugins: [barValueLabels],
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: { padding: { right: 32 } },
                    plugins: {
                        legend: { display: false },
                        tooltip: tooltip || { callbacks: { label: function (ctx) { return ctx.parsed.x + (ctx.parsed.x === 1 ? ' job' : ' jobs'); } } }
                    },
                    scales: {
                        x: countAxis(),
                        y: { grid: { display: false }, border: { display: false }, ticks: { color: gray700 } }
                    }
                }
            }));
        }

        function contractorsChart() {
            // Single series; avg cost lives in the tooltip and the table alongside.
            if (!document.getElementById('chart-contractors') || !data.contractors.length) return;
            var rows = data.contractors.map(function (r) {
                return { name: r.name, count: r.completed };
            });
            breakdownChart('chart-contractors', rows, 'name', null, {
                callbacks: {
                    label: function (ctx) { return ctx.parsed.x + ' completed'; },
                    afterLabel: function (ctx) {
                        var avg = data.contractors[ctx.dataIndex].avg_cost;
                        return avg === null ? '' : 'Avg cost: ' + gbp(avg, 2);
                    }
                }
            });
        }

        volumeChart();
        costsChart();
        breakdownChart('chart-status', data.statuses, 'status', statusColors);
        breakdownChart('chart-priority', data.priorities, 'priority', priorityColors);
        contractorsChart();
    }

    function rebuildCharts() {
        charts.forEach(function (chart) { chart.destroy(); });
        charts = [];
        buildCharts();
    }

    // Theme switches change the token values, so rebuild from scratch.
    document.addEventListener('mt:themechange', rebuildCharts);

    // Chart.js measures axis labels once and caches by font string, so charts
    // built before the Inter webfont lands keep stale (narrower) widths and
    // clip the widest tick. Build everything only after fonts are ready.
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(buildCharts);
    } else {
        buildCharts();
    }
})();
