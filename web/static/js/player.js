'use strict';
let ratingsChart = null;
let priceChart = null;
let contribChart = null;
const distributionCharts = {};
async function loadPlayer() {
    const id = window.FANTASTAT_PLAYER_ID;
    const data = await Fantastat.getJSON(Fantastat.withSeason(`/api/player/${id}`));
    const tl = await Fantastat.getJSON(Fantastat.withSeason(`/api/player/${id}/timeline`));
    const p = data.player || {}, s = data.summary || {}, records = data.records || [];
    playerName.textContent = p.name || id;
    playerMeta.textContent = [p.team_code || p.team, p.role, `season ${data.season}`, `last ${data.days}
days`].filter(Boolean).join(' | ');
    pCurrentPrice.textContent = Fantastat.fmt(s.window_QA, 0);
    pFvm.textContent = Fantastat.fmt(s.window_FVM, 0);
    pAvgFv.textContent = Fantastat.fmt(s.window_FV);
    pGoals.textContent = Fantastat.fmt(s.window_goals, 0);
    pAssists.textContent = Fantastat.fmt(s.window_assists, 0);
    addCompareBtn.onclick = () => {
        Fantastat.addCompare(p.player_id || id);
        Fantastat.toast('Added to compare')
    };
    compareLink.href = Fantastat.compareUrl([...Fantastat.compareIds(), String(p.player_id || id)]);
    renderCharts(tl.timeline || {});
    renderDistributions(s);
    renderAvailability(records);
    renderRecords(records)
}
function renderDistributionChart(canvasId, distribution, label, color = '#38bdf8') {
    const canvas = document.getElementById(canvasId);

    if (!canvas) {
        return;
    }

    if (distributionCharts[canvasId]) {
        distributionCharts[canvasId].destroy();
    }

    distributionCharts[canvasId] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: distribution.map(row => row.label),
            datasets: [
                {
                    label,
                    data: distribution.map(row => row.percentage),
                    backgroundColor: color,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: context => {
                            const row = distribution[context.dataIndex];

                            return `${row.percentage}% (${row.count})`;
                        }
                    }
                },
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#94a3b8',
                    },
                    grid: {
                        color: 'rgba(148,163,184,.08)',
                    }
                },
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        color: '#94a3b8',
                        callback: value => `${value}%`,
                    },
                    grid: {
                        color: 'rgba(148,163,184,.12)',
                    }
                }
            }
        }
    });
}
function renderDistributions(summary) {
    const d = summary.window_distributions || {};

    renderDistributionChart(
        'distGoalsChart',
        d.goals || [],
        'Goals',
        '#22c55e'
    );

    renderDistributionChart(
        'distAssistsChart',
        d.assists || [],
        'Assists',
        '#38bdf8'
    );

    renderDistributionChart(
        'distVotoChart',
        d.voto || [],
        'Voto',
        '#a78bfa'
    );

    renderDistributionChart(
        'distFantavotoChart',
        d.fantavoto || [],
        'Fantavoto',
        '#f97316'
    );

    renderDistributionChart(
        'distYellowChart',
        d.yellow_card || [],
        'Yellow card',
        '#eab308'
    );

    renderDistributionChart(
        'distRedChart',
        d.red_card || [],
        'Red card',
        '#ef4444'
    );

    renderDistributionChart(
        'distResultChart',
        d.result || [],
        'Result',
        '#14b8a6'
    );

    renderDistributionChart(
        'distStatusChart',
        d.status || [],
        'Status',
        '#64748b'
    );
}
function renderCharts(t) {
    ratingsChart && ratingsChart.destroy();
    ratingsChart = Fantastat.chartLine(ratingsChart = document.getElementById('ratingsChart'), t.matchdays || [], [{ label: 'Voto', data: t.voto || [], borderColor: '#38bdf8', backgroundColor: '#38bdf8' }, { label: 'Fantavoto', data: t.fantavoto || [], borderColor: '#f97316', backgroundColor: '#f97316' }]);
    priceChart && priceChart.destroy();
    priceChart = Fantastat.chartLine(priceChart = document.getElementById('priceChart'), t.matchdays || [], [{ label: 'Quotation', data: t.quotation || [], borderColor: '#22c55e', backgroundColor: '#22c55e' }]);
    contribChart && contribChart.destroy();
    contribChart = Fantastat.chartLine(contribChart = document.getElementById('contribChart'), t.matchdays || [], [{ label: 'Goals', data: t.goals_cumulative || [], borderColor: '#a78bfa', backgroundColor: '#a78bfa' }, { label: 'Assists', data: t.assists_cumulative || [], borderColor: '#eab308', backgroundColor: '#eab308' }])
}
function renderAvailability(records) {
    const counts = records.reduce((a, r) => {
        const k = r.status || 'Unknown';
        a[k] = (a[k] || 0) + 1;
        return a
    }, {}), total = Math.max(records.length, 1);
    availability.innerHTML = Object.entries(counts).map(([k, v]) => `<div class="status-row"><span>${k}</span><strong>${v}</strong><div class="bar"><i style="width:${100 * v / total}%"></i></div></div>`).join('') || '<p class="muted">No records in this window.</p>'
}
function renderRecords(records) {
    playerTableInfo.textContent = `${records.length}
records`;
    document.querySelector('#recordsTable tbody').innerHTML = [...records].reverse().map(r => `<tr><td>${Fantastat.fmt(r.matchday || r.giornata, 0)}</td><td>${Fantastat.fmt(r.match_text)}</td><td>${Fantastat.fmt(r.status)}</td><td class="num">${Fantastat.fmt(r.voto)}</td><td class="num strong">${Fantastat.fmt(r.fantavoto)}</td><td class="num">${Fantastat.fmt(r.scoredGoals, 0)}</td><td class="num">${Fantastat.fmt(r.assists, 0)}</td><td class="num">${Fantastat.fmt(r.quotazione_classic, 0)}</td></tr>`).join('')
}
document.addEventListener('DOMContentLoaded', async () => {
    await Fantastat.initSeasonSelector(loadPlayer);
    await loadPlayer()
});

