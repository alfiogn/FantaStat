'use strict';

let rows = [];
let topFvmChart = null;
let roleChart = null;

async function loadDashboard() {
  const season = Fantastat.selectedSeason();
  const filters = await Fantastat.getJSON(Fantastat.withSeason('/api/filters'));
  fillSelect('teamFilter', filters.teams);
  fillSelect('roleFilter', filters.roles);
  await loadSeasonStatus();
  await loadQuotations(season);
}


async function loadSeasonStatus() {
  try {
    const data = await Fantastat.getJSON(Fantastat.withSeason('/api/season-status'));
    const panel = document.getElementById('seasonStatusPanel');
    const text = document.getElementById('seasonStatusText');
    const badge = document.getElementById('seasonStatusBadge');
    if (!panel || !text || !badge) return;
    if (data.is_partial) {
      panel.classList.remove('hidden');
      badge.textContent = 'Partial';
      text.textContent = `Calendar has ${data.calendar_matchdays.length} matchdays. Player timelines are available up to matchday ${data.last_known_player_matchday || 'none yet'}. Future matchdays are handled as fixtures, not missing player data.`;
    } else {
      panel.classList.remove('hidden');
      badge.textContent = 'Complete';
      text.textContent = `Player timelines cover the available calendar matchdays for season ${data.season}.`;
    }
  } catch (err) {
    console.warn('season status unavailable', err);
  }
}

function fillSelect(id, values) {
  const el = document.getElementById(id);
  const old = el.value;
  el.innerHTML = '<option value="">All</option>' + values.map(v => `<option value="${v}">${v}</option>`).join('');
  el.value = old;
}

async function loadQuotations() {
  const params = {
    search: document.getElementById('searchInput').value.trim(),
    team: document.getElementById('teamFilter').value,
    role: document.getElementById('roleFilter').value,
    sort: document.getElementById('sortSelect').value,
    limit: 1000,
  };
  const data = await Fantastat.getJSON(Fantastat.withSeason('/api/quotations', params));
  rows = data.rows || [];
  renderStats(rows);
  renderTable(rows);
  renderCharts(rows);
}

function renderStats(data) {
  document.getElementById('statPlayers').textContent = data.length;
  document.getElementById('statTeams').textContent = new Set(data.map(r => r.team).filter(Boolean)).size;
  document.getElementById('statRoles').textContent = new Set(data.map(r => r.role).filter(Boolean)).size;
  document.getElementById('statTopFvm').textContent = data.length ? Fantastat.fmt(Math.max(...data.map(r => Number(r.FVM || 0)))) : '-';
}

function renderTable(data) {
  const n = document.getElementById('lastNInput')?.value || 38;
  document.getElementById('tableInfo').textContent = `${data.length} rows | last ${n} matchdays`;
  document.querySelector('#quotationsTable tbody').innerHTML = data.map(r => {
    const id = r.player_id || '';
    return `<tr>
      <td><a href="/player/${id}?season=${Fantastat.selectedSeason()}">${Fantastat.fmt(r.name)}</a></td>
      <td><a href="/team/${encodeURIComponent(r.team || '')}?season=${Fantastat.selectedSeason()}">${Fantastat.fmt(r.team)}</a></td>
      <td><span class="${Fantastat.roleClass(r.role)}">${Fantastat.fmt(r.role)}</span></td>
      <td class="num">${Fantastat.fmt(r.QI, 0)}</td>
      <td class="num strong">${Fantastat.fmt(r.QA, 0)}</td>
      <td class="num ${Number(r.quotation_delta || 0) >= 0 ? 'positive' : 'negative'}">${Fantastat.fmt(r.quotation_delta, 0)}</td>
      <td class="num">${Fantastat.fmt(r.FVM, 0)}</td>
      <td class="num">${Fantastat.fmt(r.window_QI, 0)}</td>
      <td class="num">${Fantastat.fmt(r.window_FV, 0)}</td>
      <td class="num">${Fantastat.fmt(r.window_FVM, 0)}</td>
      <td class="num">${Fantastat.fmt(r.window_goals, 0)}</td>
      <td class="num">${Fantastat.fmt(r.window_assists, 0)}</td>
      <td class="actions"><a class="btn small" href="/player/${id}?season=${Fantastat.selectedSeason()}">Open</a><button class="btn small secondary" onclick="addToCompare('${id}')">Compare</button></td>
    </tr>`;
  }).join('');
}

function renderCharts(data) {
  const top = [...data].sort((a, b) => Number(b.FVM || 0) - Number(a.FVM || 0)).slice(0, 12);
  if (topFvmChart) topFvmChart.destroy();
  topFvmChart = new Chart(document.getElementById('topFvmChart'), {
    type: 'bar',
    data: { labels: top.map(r => r.name), datasets: [{ label: 'FVM', data: top.map(r => r.FVM), backgroundColor: '#38bdf8' }] },
    options: chartOptions()
  });

  const counts = data.reduce((acc, r) => { acc[r.role || '?'] = (acc[r.role || '?'] || 0) + 1; return acc; }, {});
  if (roleChart) roleChart.destroy();
  roleChart = new Chart(document.getElementById('roleChart'), {
    type: 'doughnut',
    data: { labels: Object.keys(counts), datasets: [{ data: Object.values(counts), backgroundColor: ['#22c55e', '#38bdf8', '#a78bfa', '#f97316', '#64748b'] }] },
    options: { responsive: true, plugins: { legend: { labels: { color: '#dbeafe' } } } }
  });
}

function chartOptions() {
  return {
    responsive: true,
    plugins: { legend: { labels: { color: '#dbeafe' } } },
    scales: {
      x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.08)' } },
      y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' } }
    }
  };
}

function addToCompare(id) {
  Fantastat.addCompare(id);
  Fantastat.toast(`Added ${id} to compare`);
}

window.addToCompare = addToCompare;

document.addEventListener('DOMContentLoaded', async () => {
  await Fantastat.initSeasonSelector(loadDashboard);
  ['searchInput', 'teamFilter', 'roleFilter', 'sortSelect'].forEach(id => {
    document.getElementById(id).addEventListener('input', loadQuotations);
    document.getElementById(id).addEventListener('change', loadQuotations);
  });
  document.getElementById('openCompareBtn').onclick = () => window.location.href = Fantastat.compareUrl();
  document.getElementById('clearCompareBtn').onclick = () => { Fantastat.clearCompare(); Fantastat.toast('Compare cleared'); };
  await loadDashboard();
});
