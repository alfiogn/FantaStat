'use strict';
let rows = [], topFvmChart = null, roleChart = null;
let quotationRequestId = 0;
async function loadDashboard() {
    const f = await Fantastat.getJSON(Fantastat.withSeason('/api/filters'));
    fillSelect('teamFilter', f.teams);
    fillSelect('roleFilter', f.roles);
    await loadQuotations()
}
function fillSelect(id, values) {
    const e = document.getElementById(id), old = e.value;
    e.innerHTML = '<option value="">All</option>' + values.map(v => `<option value="${v}">${v}</option>`).join('');
    e.value = old
}
async function loadQuotations() {
    const requestId = ++quotationRequestId;

    const params = {
        search: document.getElementById('searchInput').value.trim(),
        team: document.getElementById('teamFilter').value,
        role: document.getElementById('roleFilter').value,
        sort: document.getElementById('sortSelect').value,
        limit: 1000,
    };

    const data =
        await Fantastat.getJSON(
            Fantastat.withSeason('/api/quotations', params)
        );

    if (requestId !== quotationRequestId) {
        return;
    }

    rows = data.rows || [];

    renderStats(rows);
    renderTable(rows, data);
    renderCharts(rows);
}
function debounce(fn, delay = 200) {
    let timer = null;

    return (...args) => {
        clearTimeout(timer);

        timer = setTimeout(() => {
            fn(...args);
        }, delay);
    };
}
function renderStats(data) {
    statPlayers.textContent = data.length;
    statTeams.textContent = new Set(data.map(r => r.team).filter(Boolean)).size;
    statRoles.textContent = new Set(data.map(r => r.role).filter(Boolean)).size;
    statTopFvm.textContent = data.length ? Fantastat.fmt(Math.max(...data.map(r => Number(r.FVM || 0))), 0) : '-'
}
function renderTable(data, payload) {
    tableInfo.textContent = `${data.length}
rows | last ${payload.days}
days`;
    document.querySelector('#quotationsTable tbody').innerHTML = data.map(r => {
        const id = r.player_id || '';
        return `<tr><td><a href="/player/${id}?season=${Fantastat.selectedSeason()}&days=${Fantastat.selectedDays()}">${Fantastat.fmt(r.name)}</a></td><td><a href="/team/${encodeURIComponent(r.team || '')}?season=${Fantastat.selectedSeason()}&days=${Fantastat.selectedDays()}">${Fantastat.fmt(r.team)}</a></td><td><span class="${Fantastat.roleClass(r.role)}">${Fantastat.fmt(r.role)}</span></td><td class="num">${Fantastat.fmt(r.QI, 0)}</td><td class="num strong">${Fantastat.fmt(r.QA, 0)}</td><td class="num ${Number(r.quotation_delta || 0) >= 0 ? 'positive' : 'negative'}">${Fantastat.fmt(r.quotation_delta, 0)}</td><td class="num">${Fantastat.fmt(r.FVM, 0)}</td><td class="num">${Fantastat.fmt(r.window_QI, 0)}</td><td class="num">${Fantastat.fmt(r.window_FV)}</td><td class="num">${Fantastat.fmt(r.window_FVM, 0)}</td><td class="num">${Fantastat.fmt(r.window_goals, 0)}</td><td class="num">${Fantastat.fmt(r.window_assists, 0)}</td><td class="actions"><a class="btn small" href="/player/${id}?season=${Fantastat.selectedSeason()}&days=${Fantastat.selectedDays()}">Open</a><button class="btn small secondary" onclick="addToCompare('${id}')">Compare</button></td></tr>`
    }).join('')
}
function renderCharts(data) {
    const top = [...data].sort((a, b) => Number(b.window_FVM || b.FVM || 0) - Number(a.window_FVM || a.FVM || 0)).slice(0, 12);
    if (topFvmChart) topFvmChart.destroy();
    topFvmChart = new Chart(topFvmChart = document.getElementById('topFvmChart'), { type: 'bar', data: { labels: top.map(r => r.name), datasets: [{ label: 'Window FVM', data: top.map(r => r.window_FVM || r.FVM), backgroundColor: '#38bdf8' }] }, options: chartOptions() });
    const counts = data.reduce((a, r) => {
        a[r.role || '?'] = (a[r.role || '?'] || 0) + 1;
        return a
    }, {});
    if (roleChart) roleChart.destroy();
    roleChart = new Chart(document.getElementById('roleChart'), {
        type: 'doughnut', data: { labels: Object.keys(counts), datasets: [{ data: Object.values(counts), backgroundColor: ['#22c55e', '#38bdf8', '#a78bfa', '#f97316', '#64748b'] }] }, options: {
            responsive: true, plugins: {
                legend: {
                    labels: { color: '#dbeafe' }
                }
            }
        }
    })
}
function chartOptions() {
    return {
        responsive: true, plugins: {
            legend: {
                labels: { color: '#dbeafe' }
            }
        }, scales: {
            x: {
                ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.08)' }
            }, y: {
                ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' }
            }
        }
    }
}
function addToCompare(id) {
    Fantastat.addCompare(id);
    Fantastat.toast(`Added ${id}
to compare`)
}
function addVisibleRowsToCompare() {
    const ids = rows
        .map(row => row.player_id)
        .filter(Boolean)
        .map(String);

    if (!ids.length) {
        Fantastat.toast('No visible players to add');
        return;
    }

    const current = Fantastat.compareIds();
    const next = [...new Set([...current, ...ids])];

    localStorage.setItem(
        'fantastat.compareIds',
        JSON.stringify(next)
    );

    Fantastat.updateCompareNav();

    Fantastat.toast(
        `Added ${ids.length} visible players to compare`
    );
}
window.addToCompare = addToCompare;
document.addEventListener('DOMContentLoaded', async () => {
    await Fantastat.initSeasonSelector(loadDashboard);
    const debouncedLoadQuotations =
    debounce(loadQuotations, 200);

    document
        .getElementById('searchInput')
        .addEventListener('input', debouncedLoadQuotations);

    document
        .getElementById('teamFilter')
        .addEventListener('change', loadQuotations);

    document
        .getElementById('roleFilter')
        .addEventListener('change', loadQuotations);

    document
        .getElementById('sortSelect')
        .addEventListener('change', loadQuotations);
    
    document
        .getElementById('addVisibleCompareBtn')
        .onclick = addVisibleRowsToCompare;
    openCompareBtn.onclick = () => location.href = Fantastat.compareUrl();
    clearCompareBtn.onclick = () => {
        Fantastat.clearCompare();
        Fantastat.toast('Compare cleared')
    };
    await loadDashboard();
});

