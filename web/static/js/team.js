'use strict';

async function loadTeam() {
  const team = window.FANTASTAT_TEAM_CODE;
  const [squad, fixtures] = await Promise.all([
    Fantastat.getJSON(Fantastat.withSeason('/api/quotations', { team, limit: 1000, sort: 'FVM' })),
    Fantastat.getJSON(Fantastat.withSeason(`/api/team/${encodeURIComponent(team)}/fixtures`)),
  ]);
  document.getElementById('teamTitle').textContent = team;
  document.querySelector('#teamSquadTable tbody').innerHTML = (squad.rows || []).map(r => `<tr><td>${r.name}</td><td>${r.role}</td><td class="num">${Fantastat.fmt(r.QA,0)}</td><td class="num">${Fantastat.fmt(r.FVM,0)}</td><td><a class="btn small" href="/player/${r.player_id}?season=${Fantastat.selectedSeason()}">Open</a></td></tr>`).join('');
  document.querySelector('#teamFixturesTable tbody').innerHTML = (fixtures.fixtures || []).map(m => `<tr><td>${m.matchday}</td><td>${m.home_team || m.team_home}</td><td>${m.away_team || m.team_away}</td><td>${score(m)}</td><td>${m.calendar_match_status || '-'}</td></tr>`).join('');
}
function score(m){return m.score_home == null ? '-' : `${m.score_home}-${m.score_away}`;}
document.addEventListener('DOMContentLoaded', async () => { await Fantastat.initSeasonSelector(loadTeam); await loadTeam(); });
