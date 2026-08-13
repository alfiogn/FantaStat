'use strict';

let lineupPayload = null;
let quotationsPayload = null;
let playerIndex = new Map();
const lineupCache = new Map();

const FORMATION_COORDS = {
  '4-3-3': [[50, 91], [80, 73, 60, 73, 40, 73, 20, 73], [70, 52, 50, 52, 30, 52], [78, 29, 50, 24, 22, 29]],
  '4-2-3-1': [[50, 91], [80, 73, 60, 73, 40, 73, 20, 73], [62, 57, 38, 57], [78, 39, 50, 36, 22, 39], [50, 22]],
  '4-4-2': [[50, 91], [80, 73, 60, 73, 40, 73, 20, 73], [80, 52, 60, 52, 40, 52, 20, 52], [60, 28, 40, 28]],
  '3-4-2-1': [[50, 91], [70, 73, 50, 73, 30, 73], [82, 53, 60, 53, 40, 53, 18, 53], [62, 35, 38, 35], [50, 20]],
  '3-5-2': [[50, 91], [70, 73, 50, 73, 30, 73], [84, 53, 67, 53, 50, 53, 33, 53, 16, 53], [60, 28, 40, 28]],
};

async function loadSeason() {

  const season =
    Fantastat.selectedSeason();
  const key = String(
    Fantastat.selectedSeason()
  );

  if (lineupCache.has(key)) {

    lineupPayload =
      lineupCache.get(key);

  } else {

    lineupPayload =
      await Fantastat.getJSON(
        Fantastat.withSeason('/api/lineups')
      );

    lineupCache.set(
      key,
      lineupPayload
    );
  }

  quotationsPayload =
    await Fantastat.getJSON(
      Fantastat.withSeason(
        '/api/quotations',
        { limit: 5000 }
      )
    );

  playerIndex =
    buildPlayerIndex(
      quotationsPayload.rows || []
    );

  fillTeams(
    lineupPayload.teams || []
  );

  renderLineups();
}

function buildPlayerIndex(rows) {
  const map = new Map();
  for (const row of rows) {
    if (!row.name) continue;
    map.set(norm(row.name), row);
    map.set(norm(row.name).replace(/\./g, ''), row);
  }
  return map;
}

function fillTeams(teams) {
  const select = document.getElementById('lineupTeam');
  const old = select.value;
  select.innerHTML = '<option value="">All</option>' + teams.map(t => `<option value="${t.team}">${t.team}</option>`).join('');
  select.value = old;
}

function renderLineups() {
  const q = norm(document.getElementById('lineupSearch').value);
  const selectedTeam = document.getElementById('lineupTeam').value;
  const teams = (lineupPayload?.teams || []).filter(t => {
    if (selectedTeam && t.team !== selectedTeam) return false;
    if (!q) return true;
    return norm(t.team).includes(q) || t.players.some(p => norm(p).includes(q));
  });

  document.getElementById('lineupsGrid').innerHTML = teams.map(renderTeam).join('');
}

function renderTeam(team) {
  const module = team.module || '4-3-3';
  const players = flattenGroups(team.groups || []);
  const coords = coordsFor(module, players.length);
  const nodes = players.map((player, i) => renderPlayerNode(player, coords[i] || [50, 50])).join('');

  return `<article class="lineup-card">
    <div class="lineup-header">
      <div><h2>${team.team}</h2><p class="muted">${team.coach || ''}</p></div>
      <span class="module-pill">${team.module_text || module}</span>
    </div>
    <div class="pitch-wrap">
      <div class="pitch">
        <div class="pitch-line box top"></div><div class="pitch-line box bottom"></div>
        <div class="pitch-line mid"></div><div class="pitch-line circle"></div>
        ${nodes}
      </div>
    </div>
    <div class="lineup-meta">
      <p><strong>Ballottaggi</strong>: ${team.ballottaggi || '-'}</p>
      <p><strong>Rigoristi</strong>: ${team.rigoristi || '-'}</p>
      <p><strong>Calci da fermo</strong>: ${team.calci_da_fermo || '-'}</p>
    </div>
  </article>`;
}

function renderPlayerNode(player, coord) {
  const match = findPlayer(player);
  const disabled = match ? '' : 'disabled';
  const id = match?.player_id || '';
  return `<div class="lineup-player" style="left:${coord[0]}%;top:${coord[1]}%" data-player="${player}">
    <button class="player-dot" onclick="openLineupPlayer('${escapeJs(player)}')">${initials(player)}</button>
    <div class="player-name">${player}</div>
    <div class="player-actions">
      <button ${disabled} onclick="openLineupPlayer('${escapeJs(player)}')">Open</button>
      <button ${disabled} onclick="compareLineupPlayer('${escapeJs(player)}')">Compare</button>
    </div>
  </div>`;
}

function coordsFor(module, count) {
  const rows = FORMATION_COORDS[module] || FORMATION_COORDS['4-3-3'];
  const coords = [];
  for (const row of rows) {
    for (let i = 0; i < row.length; i += 2) coords.push([row[i], row[i + 1]]);
  }
  if (coords.length >= count) return coords.slice(0, count);
  while (coords.length < count) coords.push([50, 50]);
  return coords;
}

function flattenGroups(groups) {
  return groups.flatMap(g => g);
}

function findPlayer(name) {
  return playerIndex.get(norm(name)) || playerIndex.get(norm(name).replace(/\./g, '')) || null;
}

function openLineupPlayer(name) {
  const player = findPlayer(name);
  if (!player) return Fantastat.toast(`No Mongo match for ${name}`);
  window.location.href = `/player/${player.player_id}?season=${Fantastat.selectedSeason()}&days=${Fantastat.selectedDays()}`;
}

function compareLineupPlayer(name) {
  const player = findPlayer(name);
  if (!player) return Fantastat.toast(`No Mongo match for ${name}`);
  Fantastat.addCompare(player.player_id);
  Fantastat.toast(`${name} added to compare`);
}

function norm(value) {
  return String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
}

function initials(value) {
  return String(value || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase();
}

function escapeJs(value) {
  return String(value).replace(/'/g, "\\'");
}

window.openLineupPlayer = openLineupPlayer;
window.compareLineupPlayer = compareLineupPlayer;

document.addEventListener(
  'DOMContentLoaded',
  async () => {
    await Fantastat.initSeasonSelector(
      loadSeason
    );

    document
      .getElementById('lineupSearch')
      .addEventListener(
        'input',
        renderLineups
      );

    document
      .getElementById('lineupTeam')
      .addEventListener(
        'change',
        renderLineups
      );

    await loadSeason();
  }
);
