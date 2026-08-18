'use strict';

let rows = [];
let visibleRows = [];
let notesByPlayer = {};
let topFvmChart = null;
let roleChart = null;
let quotationRequestId = 0;
let currentNotePlayerId = null;

async function loadDashboard() {
    const filters = await Fantastat.getJSON(
        Fantastat.withSeason('/api/filters')
    );

    fillSelect('teamFilter', filters.teams || []);
    fillSelect('roleFilter', filters.roles || []);

    await loadNotes();
    await loadQuotations();
}

async function loadNotes() {
    try {
        notesByPlayer = await Fantastat.getJSON('/api/notes');
    } catch {
        notesByPlayer = {};
    }
}

function fillSelect(id, values) {
    const element = document.getElementById(id);
    if (!element) return;

    const old = element.value;
    element.innerHTML = [
        '<option value="">All</option>',
        ...values.map(value =>
            `<option value="${escapeAttr(value)}">${Fantastat.fmt(value)}</option>`
        ),
    ].join('');
    element.value = old;
}

async function loadQuotations() {
    const requestId = ++quotationRequestId;

    const params = {
        search: valueOf('searchInput').trim(),
        team: valueOf('teamFilter'),
        role: valueOf('roleFilter'),
        sort: valueOf('sortSelect') || 'FVM',
        limit: 1000,
    };

    const payload = await Fantastat.getJSON(
        Fantastat.withSeason('/api/quotations', params)
    );

    if (requestId !== quotationRequestId) return;

    rows = (payload.rows || []).map(enrichRow);
    refreshDashboard(payload);
}

function enrichRow(row) {
    const qa = numberOrNull(row.QA);
    const wQi = numberOrNull(row.window_QI);
    const playerId = row.player_id == null ? '' : String(row.player_id);
    const note = notesByPlayer[playerId] || notesByPlayer[row.name] || '';

    return {
        ...row,
        note,
        window_delta: qa == null || wQi == null ? null : qa - wQi,
    };
}

function refreshDashboard(payload = {}) {
    visibleRows = applyLocalFilters(rows);
    renderStats(visibleRows);
    renderTable(visibleRows, payload);
    renderCharts(visibleRows);
}

function applyLocalFilters(data) {
    const minQa = numberOrNull(valueOf('minQaFilter'));
    const maxQa = numberOrNull(valueOf('maxQaFilter'));
    const minWDelta = numberOrNull(valueOf('minWDeltaFilter'));
    const maxWDelta = numberOrNull(valueOf('maxWDeltaFilter'));
    const withNotes = boolOf('withNotesFilter');

    return data.filter(row => {
        const qa = numberOrNull(row.QA);
        const delta = numberOrNull(row.window_delta);

        if (minQa != null && (qa == null || qa < minQa)) return false;
        if (maxQa != null && (qa == null || qa > maxQa)) return false;
        if (minWDelta != null && (delta == null || delta < minWDelta)) return false;
        if (maxWDelta != null && (delta == null || delta > maxWDelta)) return false;
        if (withNotes && !String(row.note || '').trim()) return false;

        return true;
    });
}

function comparePlayers(playerId) {
    Fantastat.addCompare(playerId);
    Fantastat.toast('Added to compare');
};

function showNote(playerId) {
    const row = rows.find(
        item => String(item.player_id) === String(playerId)
    );

    openNoteModal(
        playerId,
        row?.name || playerId
    );
};

function renderStats(data) {
    statPlayers.textContent = data.length;
    statTeams.textContent = new Set(data.map(r => r.team).filter(Boolean)).size;
    statRoles.textContent = new Set(data.map(r => r.role).filter(Boolean)).size;
    statTopFvm.textContent = data.length
        ? Fantastat.fmt(Math.max(...data.map(r => Number(r.FVM || 0))), 0)
        : '-';
}

function renderTable(data, payload) {
    tableInfo.textContent = `${data.length} rows | last ${payload.days || Fantastat.selectedDays()} days`;

    document.querySelector('#quotationsTable tbody').innerHTML = data.map(row => {
        const id = row.player_id || '';
        const season = Fantastat.selectedSeason();
        const days = Fantastat.selectedDays();
        const playerUrl = `/player/${id}?season=${season}&days=${days}`;
        const teamUrl = `/team/${encodeURIComponent(row.team || '')}?season=${season}&days=${days}`;

        return `
            <tr>
                <td><a href="${playerUrl}">${Fantastat.fmt(row.name)}</a></td>
                <td><a href="${teamUrl}">${Fantastat.fmt(row.team)}</a></td>
                <td>${Fantastat.fmt(row.role)}</td>
                <td class="num">${Fantastat.fmt(row.QI, 0)}</td>
                <td class="num strong">${Fantastat.fmt(row.QA, 0)}</td>
                <td class="num ${classFor(row.quotation_delta)}">${Fantastat.fmt(row.quotation_delta, 0)}</td>
                <td class="num">${Fantastat.fmt(row.FVM, 0)}</td>
                <td class="num">${Fantastat.fmt(row.window_QI, 0)}</td>
                <td class="num ${classFor(row.window_delta)}">${Fantastat.fmt(row.window_delta, 1)}</td>
                <td class="num">${Fantastat.fmt(row.window_FV)}</td>
                <td class="num">${Fantastat.fmt(row.window_MV)}</td>
                <td class="num">${Fantastat.fmt(row.window_goals, 0)}</td>
                <td class="num">${Fantastat.fmt(row.window_assists, 0)}</td>
                <td class="note-cell">${shortNote(row.note)}</td>
                <td class="actions">
                    <a href="${playerUrl}" class="btn btn-sm btn-outline-primary">Open</a>
                    <button class="btn btn-sm btn-outline-secondary" onclick="addCompare('${row.player_id}')">Compare</button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="showNote('${row.player_id}')">Note</button>
                </td>
            </tr>
        `;
        
    }).join('');
}

function renderCharts(data) {
    const top = [...data]
        .sort((a, b) => Number(b.FVM || 0) - Number(a.FVM || 0))
        .slice(0, 15);

    const topCtx = document.getElementById('topFvmChart');
    if (topCtx) {
        topFvmChart && topFvmChart.destroy();
        topFvmChart = new Chart(topCtx, {
            type: 'bar',
            data: {
                labels: top.map(r => r.name),
                datasets: [{ label: 'FVM', data: top.map(r => r.FVM || 0), backgroundColor: '#38bdf8' }],
            },
            options: chartOptions(false),
        });
    }

    const counts = data.reduce((acc, row) => {
        const role = row.role || 'Unknown';
        acc[role] = (acc[role] || 0) + 1;
        return acc;
    }, {});

    const roleCtx = document.getElementById('roleChart');
    if (roleCtx) {
        roleChart && roleChart.destroy();
        roleChart = new Chart(roleCtx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(counts),
                datasets: [{ data: Object.values(counts), backgroundColor: ['#16a34a', '#0284c7', '#7c3aed', '#ea580c', '#64748b'] }],
            },
            options: chartOptions(true),
        });
    }
}

function chartOptions(showLegend) {
    return {
        responsive: true,
        plugins: {
            legend: { display: showLegend, labels: { color: '#cbd5e1' } },
        },
        scales: showLegend ? {} : {
            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.08)' } },
            y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' } },
        },
    };
}

function openNoteModal(playerId, playerName) {
    currentNotePlayerId = String(playerId);
    notePlayer.textContent = playerName || playerId;
    noteText.value = notesByPlayer[currentNotePlayerId] || '';
    noteModal.classList.remove('hidden');
    noteText.focus();
}

async function saveCurrentNote() {
    if (!currentNotePlayerId) return;

    const note = noteText.value.trim();
    await fetch(`/api/notes/${encodeURIComponent(currentNotePlayerId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note }),
    });

    notesByPlayer[currentNotePlayerId] = note;
    noteModal.classList.add('hidden');
    rows = rows.map(enrichRow);
    refreshDashboard();
}

function exportExcel() {
    const params = new URLSearchParams({
        season: Fantastat.selectedSeason(),
        days: Fantastat.selectedDays(),
        search: valueOf('searchInput').trim(),
        team: valueOf('teamFilter'),
        role: valueOf('roleFilter'),
        sort: valueOf('sortSelect') || 'FVM',
    });
    window.location.href = `/api/export/dashboard.xlsx?${params.toString()}`;
}

function shortNote(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    return text.length > 48 ? `${escapeHtml(text.slice(0, 48))}...` : escapeHtml(text);
}

function classFor(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number === 0) return '';
    return number > 0 ? 'positive' : 'negative';
}

function valueOf(id) {
    const element = document.getElementById(id);
    return element ? element.value : '';
}

function boolOf(id) {
    const element = document.getElementById(id);
    return Boolean(element && element.checked);
}

function numberOrNull(value) {
    if (value === '' || value == null) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value);
}

function debounce(fn, delay = 200) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

document.addEventListener('DOMContentLoaded', async () => {
    await Fantastat.initSeasonSelector(loadDashboard);
    await loadDashboard();

    searchInput.addEventListener('input', debounce(loadQuotations));
    teamFilter.addEventListener('change', loadQuotations);
    roleFilter.addEventListener('change', loadQuotations);
    sortSelect.addEventListener('change', loadQuotations);

    ['minQaFilter', 'maxQaFilter', 'minWDeltaFilter', 'maxWDeltaFilter', 'withNotesFilter']
        .forEach(id => {
            const element = document.getElementById(id);
            if (element) element.addEventListener('input', () => refreshDashboard());
            if (element) element.addEventListener('change', () => refreshDashboard());
        });

    document.querySelector('#quotationsTable tbody').addEventListener('click', event => {
        const button = event.target.closest('button[data-action]');
        if (!button) return;

        const playerId = button.dataset.playerId;
        if (button.dataset.action === 'compare') {
            Fantastat.addCompare(playerId);
            Fantastat.toast('Added to compare');
        }
        if (button.dataset.action === 'note') {
            openNoteModal(playerId, button.dataset.playerName);
        }
    });

    saveNoteBtn.addEventListener('click', saveCurrentNote);
    closeNoteBtn.addEventListener('click', () => noteModal.classList.add('hidden'));
    exportExcelBtn.addEventListener('click', exportExcel);

    clearCompareBtn.addEventListener('click', () => {
        Fantastat.clearCompare();
        Fantastat.toast('Compare cleared');
    });

    openCompareBtn.addEventListener('click', () => {
        window.location.href = Fantastat.compareUrl(Fantastat.compareIds());
    });

    addVisibleCompareBtn.addEventListener('click', () => {
        visibleRows.forEach(row => {
            if (row.player_id) Fantastat.addCompare(row.player_id);
        });
        Fantastat.toast(`Added ${visibleRows.length} players`);
    });
});
