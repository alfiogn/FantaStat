'use strict';

let fvChart = null;
let priceChart = null;

function idsFromPage() {
  const fromTemplate = window.FANTASTAT_COMPARE_IDS || [];
  return fromTemplate.length ? fromTemplate : Fantastat.compareIds();
}

async function loadCompare() {
  const ids = idsFromPage();
  if (!ids.length) {
    document.getElementById('compareCards').innerHTML = '<p class="muted">No selected players. Add players from the dashboard.</p>';
    return;
  }
  const params = new URLSearchParams();
  ids.forEach(id => params.append('id', id));
  const season = Fantastat.selectedSeason();
  if (season) params.set('season', season);
  const days = Fantastat.selectedDays();
  if (days) params.set('days', days);
  const data = await Fantastat.getJSON('/api/compare?' + params.toString());
  renderCards(data.players || []);
  renderMetrics(data.metrics || [], data.players || []);
  renderCharts(data.players || []);
}

function renderCards(players) {
  document.getElementById('compareCards').innerHTML = players.map(p => `<article class="compare-card">
    <h3><a href="/player/${p.player_id}?season=${Fantastat.selectedSeason()}">${p.name}</a></h3>
    <p class="muted">${[p.team, p.role].filter(Boolean).join(' | ')}</p>
    <div class="mini-stats"><span>FV <b>${Fantastat.fmt(p.summary.avg_fantavote)}</b></span><span>G <b>${Fantastat.fmt(p.summary.goals,0)}</b></span><span>A <b>${Fantastat.fmt(p.summary.assists,0)}</b></span></div>
  </article>`).join('');
}

function renderMetrics(metrics, players) {
  document.querySelector('#metricsTable thead').innerHTML = '<tr><th>Metric</th>' + players.map(p => `<th>${p.name}</th>`).join('') + '</tr>';
  document.querySelector('#metricsTable tbody').innerHTML = metrics.map(m => `<tr><td>${m}</td>${players.map(p => `<td class="num">${Fantastat.fmt(p.summary[m])}</td>`).join('')}</tr>`).join('');
}

function renderCharts(players) {
  const colors = ['#38bdf8', '#f97316', '#22c55e', '#a78bfa', '#eab308', '#ef4444'];
  const labels = players[0]?.timeline?.matchdays || [];
  if (fvChart) fvChart.destroy();
  fvChart = Fantastat.chartLine(document.getElementById('compareFvChart'), labels, players.map((p, i) => ({ label: p.name, data: p.timeline.fantavoto || [], borderColor: colors[i % colors.length], backgroundColor: colors[i % colors.length] })));
  if (priceChart) priceChart.destroy();
  priceChart = Fantastat.chartLine(document.getElementById('comparePriceChart'), labels, players.map((p, i) => ({ label: p.name, data: p.timeline.quotation || [], borderColor: colors[i % colors.length], backgroundColor: colors[i % colors.length] })));
}

document.addEventListener('DOMContentLoaded', async () => {
  await Fantastat.initSeasonSelector(loadCompare);
  document.getElementById('clearComparePageBtn').onclick = () => { Fantastat.clearCompare(); window.location.href = '/compare'; };
  await loadCompare();
});
