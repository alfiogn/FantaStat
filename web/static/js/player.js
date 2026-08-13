'use strict';

let ratingsChart = null;
let priceChart = null;
let contribChart = null;

async function loadPlayer() {
  const playerId = window.FANTASTAT_PLAYER_ID;
  const data = await Fantastat.getJSON(Fantastat.withSeason(`/api/player/${playerId}`));
  const timelineData = await Fantastat.getJSON(Fantastat.withSeason(`/api/player/${playerId}/timeline`));
  const player = data.player || {};
  const seasonData = data.season_data || {};
  const summary = seasonData.summary || {};
  const records = seasonData.records || [];

  document.getElementById('playerName').textContent = player.name || playerId;
  document.getElementById('playerMeta').textContent = [player.team_code || player.team, player.role, `season ${data.season}`].filter(Boolean).join(' | ');
  document.getElementById('pCurrentPrice').textContent = Fantastat.fmt(summary.current_price, 0);
  document.getElementById('pFvm').textContent = Fantastat.fmt(summary.fvm, 0);
  document.getElementById('pAvgFv').textContent = Fantastat.fmt(summary.avg_fantavote);
  document.getElementById('pGoals').textContent = Fantastat.fmt(summary.goals, 0);
  document.getElementById('pAssists').textContent = Fantastat.fmt(summary.assists, 0);

  document.getElementById('addCompareBtn').onclick = () => { Fantastat.addCompare(player.player_id || playerId); Fantastat.toast('Added to compare'); };
  document.getElementById('compareLink').href = Fantastat.compareUrl([...Fantastat.compareIds(), String(player.player_id || playerId)]);

  renderCharts(trimTimeline(timelineData.timeline || {}));
  await renderSeasonStatus(playerId);
  const n = Number(document.getElementById('playerLastNInput')?.value || 38);
  const lastRecords = sortedLast(records, n);
  renderAvailability(records);
  renderRecords(records);
}

function trimTimeline(t) {
  const n = Number(document.getElementById('playerLastNInput')?.value || 38);
  const out = {};
  for (const [k, v] of Object.entries(t)) {
    out[k] = Array.isArray(v) ? v.slice(-n) : v;
  }
  return out;
}

function sortedLast(records, n) {
  return [...records]
    .sort((a, b) => Number(a.matchday || a.giornata || 0) - Number(b.matchday || b.giornata || 0))
    .slice(-n);
}

function renderCharts(t) {
  if (ratingsChart) ratingsChart.destroy();
  ratingsChart = Fantastat.chartLine(document.getElementById('ratingsChart'), t.matchdays || [], [
    { label: 'Voto', data: t.voto || [], borderColor: '#38bdf8', backgroundColor: '#38bdf8' },
    { label: 'Fantavoto', data: t.fantavoto || [], borderColor: '#f97316', backgroundColor: '#f97316' },
  ]);
  if (priceChart) priceChart.destroy();
  priceChart = Fantastat.chartLine(document.getElementById('priceChart'), t.matchdays || [], [
    { label: 'Quotation', data: t.quotation || [], borderColor: '#22c55e', backgroundColor: '#22c55e' },
  ]);
  if (contribChart) contribChart.destroy();
  contribChart = Fantastat.chartLine(document.getElementById('contribChart'), t.matchdays || [], [
    { label: 'Goals', data: t.goals_cumulative || [], borderColor: '#a78bfa', backgroundColor: '#a78bfa' },
    { label: 'Assists', data: t.assists_cumulative || [], borderColor: '#eab308', backgroundColor: '#eab308' },
  ]);
}


async function renderSeasonStatus(playerId) {
  try {
    const data = await Fantastat.getJSON(Fantastat.withSeason(`/api/player/${playerId}/season-status`));
    const panel = document.getElementById('playerSeasonStatusPanel');
    const text = document.getElementById('playerSeasonStatusText');
    const badge = document.getElementById('playerSeasonStatusBadge');
    if (panel && text && badge) {
      panel.classList.remove('hidden');
      badge.textContent = data.is_partial ? 'Partial' : 'Complete';
      text.textContent = data.is_partial
        ? `Timeline data available up to matchday ${data.last_known_player_matchday || 'none yet'}. Calendar has ${data.last_calendar_matchday || 0} matchdays. Future rounds below come from the calendar.`
        : `Timeline data covers the available calendar matchdays.`;
    }
    renderNextFixtures(data.next_fixtures || []);
  } catch (err) {
    console.warn('player season status unavailable', err);
  }
}

function renderNextFixtures(fixtures) {
  const body = document.querySelector('#nextFixturesTable tbody');
  if (!body) return;
  body.innerHTML = fixtures.map(m => `<tr>
    <td>${Fantastat.fmt(m.matchday || m.giornata, 0)}</td>
    <td>${Fantastat.fmt(m.home_team || m.team_home)}</td>
    <td>${Fantastat.fmt(m.away_team || m.team_away)}</td>
    <td>${Fantastat.fmt(m.match_date || m.date)}</td>
    <td>${Fantastat.fmt(m.calendar_match_status)}</td>
  </tr>`).join('') || '<tr><td colspan="5" class="muted">No future fixtures found.</td></tr>';
}

function renderAvailability(records) {
  const counts = records.reduce((acc, r) => { const k = r.status || 'Unknown'; acc[k] = (acc[k] || 0) + 1; return acc; }, {});
  const total = Math.max(records.length, 1);
  document.getElementById('availability').innerHTML = Object.entries(counts).map(([k, v]) => `
    <div class="status-row"><span>${k}</span><strong>${v}</strong><div class="bar"><i style="width:${100*v/total}%"></i></div></div>
  `).join('') || '<p class="muted">No records yet.</p>';
}

function renderRecords(records) {
  const last = [...records].sort((a, b) => Number(b.matchday || b.giornata || 0) - Number(a.matchday || a.giornata || 0)).slice(0, 12);
  document.getElementById('playerTableInfo').textContent = `${records.length} records`;
  document.querySelector('#recordsTable tbody').innerHTML = last.map(r => `<tr>
    <td>${Fantastat.fmt(r.matchday || r.giornata, 0)}</td>
    <td>${Fantastat.fmt(r.match_text)}</td>
    <td>${Fantastat.fmt(r.status)}</td>
    <td class="num">${Fantastat.fmt(r.voto)}</td>
    <td class="num strong">${Fantastat.fmt(r.fantavoto)}</td>
    <td class="num">${Fantastat.fmt(r.scoredGoals, 0)}</td>
    <td class="num">${Fantastat.fmt(r.assists, 0)}</td>
    <td class="num">${Fantastat.fmt(r.quotazione_classic, 0)}</td>
  </tr>`).join('');
}

document.getElementById('playerLastNInput')?.addEventListener('change', loadPlayer);
document.getElementById('playerLastNInput')?.addEventListener('input', loadPlayer);
document.addEventListener('DOMContentLoaded', async () => {
  await Fantastat.initSeasonSelector(loadPlayer);
  await loadPlayer();
});
