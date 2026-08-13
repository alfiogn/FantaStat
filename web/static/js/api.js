'use strict';

window.Fantastat = (() => {
  const state = { season: null };

  function qs(name, fallback = '') {
    return new URLSearchParams(window.location.search).get(name) || fallback;
  }

  function selectedSeason() {
    const urlSeason = qs('season');
    if (urlSeason) return Number(urlSeason);
    const sel = document.getElementById('globalSeason');
    if (sel && sel.value) return Number(sel.value);
    return state.season;
  }

  function selectedDays() {
    const urlDays = qs('days') || qs('last_n_days');
    if (urlDays) return Number(urlDays);
    const input = document.getElementById('globalDays');
    if (input && input.value) return Number(input.value);
    return state.days || 38;
  }

  async function getJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
    return await res.json();
  }

  function withSeason(path, params = {}) {
    const url = new URL(path, window.location.origin);
    const season = selectedSeason();
    const days = selectedDays();
    if (days) url.searchParams.set('days', days);
    if (season) url.searchParams.set('season', season);
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    }
    return url.pathname + url.search;
  }

  async function initSeasonSelector(onChange) {
    const sel = document.getElementById('globalSeason');
    if (!sel) return null;
    const daysInput = document.getElementById('globalDays');
    if (daysInput) {
      daysInput.value = qs('days', qs('last_n_days', '38'));
      state.days = Number(daysInput.value || 38);
      daysInput.addEventListener('change', () => { state.days = Number(daysInput.value || 38); if (onChange) onChange(state.season); });
      daysInput.addEventListener('input', () => { state.days = Number(daysInput.value || 38); if (onChange) onChange(state.season); });
    }
    const seasons = await getJSON('/api/seasons');
    const defaultSeason = sel.dataset.defaultSeason || seasons[0] || '';
    sel.innerHTML = seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    sel.value = qs('season', defaultSeason);
    state.season = Number(sel.value);
    sel.addEventListener('change', () => {
      state.season = Number(sel.value);
      if (onChange) onChange(state.season);
    });
    return state.season;
  }

  function fmt(value, digits = 2) {
    if (value === null || value === undefined || value === '') return '-';
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(digits);
    return String(value);
  }

  function roleClass(role) {
    return `role role-${String(role || 'x').toLowerCase()}`;
  }

  function compareIds() {
    return JSON.parse(localStorage.getItem('fantastat.compareIds') || '[]');
  }

  function saveCompareIds(ids) {
    const clean = [...new Set(ids.filter(Boolean).map(String))].slice(0, 6);
    localStorage.setItem('fantastat.compareIds', JSON.stringify(clean));
    updateCompareNav();
    return clean;
  }

  function addCompare(id) {
    const ids = compareIds();
    if (!ids.includes(String(id))) ids.push(String(id));
    return saveCompareIds(ids);
  }

  function clearCompare() { return saveCompareIds([]); }

  function compareUrl(ids = compareIds()) {
    const url = new URL('/compare', window.location.origin);
    for (const id of ids) url.searchParams.append('id', id);
    const season = selectedSeason();
    if (season) url.searchParams.set('season', season);
    return url.pathname + url.search;
  }

  function updateCompareNav() {
    const nav = document.getElementById('navCompare');
    if (nav) nav.href = compareUrl();
  }

  function toast(message) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 2200);
  }

  function chartLine(ctx, labels, datasets) {
    return new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        tension: 0.25,
        spanGaps: true,
        plugins: { legend: { labels: { color: '#dbeafe' } } },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' } }
        }
      }
    });
  }

  updateCompareNav();
  return { getJSON, withSeason, initSeasonSelector, selectedDays, selectedSeason, fmt, roleClass, addCompare, clearCompare, compareIds, compareUrl, updateCompareNav, toast, chartLine };
})();
