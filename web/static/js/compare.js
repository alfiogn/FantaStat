'use strict';

let fvChart = null;
let priceChart = null;
let comparePayload = null;
let compareDistributionChart = null;

function idsFromPage() {
    const fromTemplate = window.FANTASTAT_COMPARE_IDS || [];
    return fromTemplate.length ? fromTemplate : Fantastat.compareIds();
}

function selectedRoles() {
    return [...document.querySelectorAll('.compare-role-filter:checked')]
        .map(input => input.value);
}

function filteredPlayers() {
    const roles = selectedRoles();

    return (comparePayload?.players || [])
        .filter(player => roles.includes(String(player.role || '')));
}

async function loadCompare() {
    const ids = idsFromPage();

    if (!ids.length) {
        document.getElementById('compareCards').innerHTML =
            '<p class="muted">No selected players. Add players from the dashboard or lineups page.</p>';
        return;
    }

    const params = new URLSearchParams();

    ids.forEach(id => params.append('id', id));
    params.set('season', Fantastat.selectedSeason());
    params.set('days', Fantastat.selectedDays());

    comparePayload =
        await Fantastat.getJSON('/api/compare?' + params.toString());

    renderCompare();
}

function renderCompareDistribution(players) {
    const select = document.getElementById('compareDistributionMetric');

    if (!select) {
        return;
    }

    const metric = select.value;
    const canvas = document.getElementById('compareDistributionChart');

    if (!canvas) {
        return;
    }

    const labelSet = new Set();

    for (const player of players) {
        const distribution =
            player.summary.window_distributions?.[metric] || [];

        for (const row of distribution) {
            labelSet.add(row.label);
        }
    }

    const labels = [...labelSet];

    const colors = [
        '#38bdf8',
        '#f97316',
        '#22c55e',
        '#a78bfa',
        '#eab308',
        '#ef4444',
        '#14b8a6',
        '#64748b',
    ];

    const datasets = players.map((player, index) => {
        const distribution =
            player.summary.window_distributions?.[metric] || [];

        const byLabel = new Map(
            distribution.map(row => [row.label, row.percentage])
        );

        return {
            label: player.name,
            data: labels.map(label => byLabel.get(label) || 0),
            backgroundColor: colors[index % colors.length],
        };
    });

    if (compareDistributionChart) {
        compareDistributionChart.destroy();
    }

    compareDistributionChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets,
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: {
                        color: '#dbeafe',
                    }
                },
                tooltip: {
                    callbacks: {
                        label: context => {
                            return `${context.dataset.label}: ${context.raw}%`;
                        }
                    }
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

function renderCompare() {
    const players = filteredPlayers();

    renderCards(players);
    renderMetrics(comparePayload?.metrics || [], players);
    renderCharts(players);
    renderCompareDistribution(players);
}

function renderCards(players) {
    const container = document.getElementById('compareCards');

    if (!players.length) {
        container.innerHTML =
            '<p class="muted">No players visible with current role filters.</p>';
        return;
    }

    container.innerHTML = players.map(player => `
        <article class="compare-card">
            <button
                class="compare-remove"
                onclick="removeComparedPlayer('${player.player_id}')"
                title="Remove from comparison"
            >
                ×
            </button>

            <h3>
                <a href="/player/${player.player_id}?days=${Fantastat.selectedDays()}">
                    ${player.name}
                </a>
            </h3>

            <p class="muted">
                ${[player.team, player.role].filter(Boolean).join(' | ')}
            </p>

            <div class="mini-stats">
                <span>FV <b>${Fantastat.fmt(player.summary.window_FV)}</b></span>
                <span>MV <b>${Fantastat.fmt(player.summary.window_MV)}</b></span>
                <span>G <b>${Fantastat.fmt(player.summary.window_goals, 0)}</b></span>
                <span>A <b>${Fantastat.fmt(player.summary.window_assists, 0)}</b></span>
            </div>
        </article>
    `).join('');
}

function renderMetrics(metrics, players) {
    const table = document.getElementById('metricsTable');

    table.querySelector('thead').innerHTML =
        '<tr><th>Metric</th>' +
        players.map(player => `<th>${player.name}</th>`).join('') +
        '</tr>';

    table.querySelector('tbody').innerHTML =
        metrics.map(metric => `
            <tr>
                <td>${metric}</td>
                ${players.map(player => `
                    <td class="num">${Fantastat.fmt(player.summary[metric])}</td>
                `).join('')}
            </tr>
        `).join('');
}

function renderCharts(players) {
    const colors = [
        '#38bdf8',
        '#f97316',
        '#22c55e',
        '#a78bfa',
        '#eab308',
        '#ef4444',
        '#14b8a6',
        '#f43f5e'
    ];

    const labels = players[0]?.timeline?.matchdays || [];

    if (fvChart) {
        fvChart.destroy();
    }

    fvChart = Fantastat.chartLine(
        document.getElementById('compareFvChart'),
        labels,
        players.map((player, index) => ({
            label: player.name,
            data: player.timeline.fantavoto || [],
            borderColor: colors[index % colors.length],
            backgroundColor: colors[index % colors.length]
        }))
    );

    if (priceChart) {
        priceChart.destroy();
    }

    priceChart = Fantastat.chartLine(
        document.getElementById('comparePriceChart'),
        labels,
        players.map((player, index) => ({
            label: player.name,
            data: player.timeline.quotation || [],
            borderColor: colors[index % colors.length],
            backgroundColor: colors[index % colors.length]
        }))
    );
}

function removeComparedPlayer(playerId) {
    Fantastat.removeCompare(playerId);

    if (comparePayload) {
        comparePayload.players =
            comparePayload.players.filter(
                player => String(player.player_id) !== String(playerId)
            );
    }

    renderCompare();
    Fantastat.toast('Player removed');
}

window.removeComparedPlayer = removeComparedPlayer;

document.addEventListener('DOMContentLoaded', async () => {
    await Fantastat.initSeasonSelector(loadCompare);

    document
        .querySelectorAll('.compare-role-filter')
        .forEach(input => {
            input.addEventListener('change', renderCompare);
        });

    document.getElementById('clearComparePageBtn').onclick = () => {
        Fantastat.clearCompare();
        window.location.href = '/compare';
    };

    document
        .getElementById('compareDistributionMetric')
        ?.addEventListener('change', renderCompare);

    await loadCompare();
});