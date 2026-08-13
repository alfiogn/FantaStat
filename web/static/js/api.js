'use strict';

window.Fantastat = (() => {
    let pendingRequests = 0;
    let spinnerTimer = null;

    function showLoader() {
        pendingRequests++;

        spinnerTimer = setTimeout(() => {
            document
                .getElementById("loadingOverlay")
                ?.classList.remove("hidden");
        }, 150);
    }

    function hideLoader() {
        pendingRequests--;

        if (pendingRequests <= 0) {
            pendingRequests = 0;

            clearTimeout(spinnerTimer);

            document
                .getElementById("loadingOverlay")
                ?.classList.add("hidden");
        }
    }

    const state = { season: null, days: 38 };
    function qs(n, f = '') { return new URLSearchParams(location.search).get(n) || f }
    function selectedSeason() {
        const u = qs('season');

        if (u) return Number(u);
        const s = document.getElementById('globalSeason');
        return s && s.value ? Number(s.value) : state.season
    }

    function selectedDays() {
        const u = qs('days', qs('last_n_days'));
        if (u) return Number(u);
        const d = document.getElementById('globalDays');
        return d && d.value ? Number(d.value) : state.days
    }

    async function getJSON(url) {
        showLoader();

        try {
            const res = await fetch(url);

            if (!res.ok) {
                throw new Error(
                    `${res.status} ${res.statusText}: ${url}`
                );
            }

            return await res.json();
        }
        finally {
            hideLoader();
        }
    }

    function withSeason(path, params = {}) {
        const u = new URL(path, location.origin);
        const s = selectedSeason();
        const d = selectedDays();
        if (s) u.searchParams.set('season', s);
        if (d) u.searchParams.set('days', d);
        for (const [k, v] of Object.entries(params)) { if (v !== undefined && v !== null && v !== '') u.searchParams.set(k, v) }
        return u.pathname + u.search
    }

    async function initSeasonSelector(onChange) {
        const s = document.getElementById('globalSeason');
        if (!s) return null;
        const seasons = await getJSON('/api/seasons');
        const def = s.dataset.defaultSeason || seasons[0] || '';
        s.innerHTML = seasons.map(x => `<option value="${x}">${x}</option>`).join('');
        s.value = qs('season', def);
        state.season = Number(s.value);
        s.addEventListener('change', () => {
            state.season = Number(s.value);
            onChange && onChange(state.season);
            updateWindowInfo()
        });
        const d = document.getElementById('globalDays');
        if (d) {
            d.value = qs('days', qs('last_n_days', '38'));
            state.days = Number(d.value || 38);
            d.addEventListener('change', () => {
                state.days = Number(d.value || 38);
                onChange && onChange(state.season);
                updateWindowInfo()
            });
            d.addEventListener('input', () => {
                state.days = Number(d.value || 38);
                onChange && onChange(state.season)
            })
        }
        await updateWindowInfo();
        updateCompareNav();
        return state.season
    }

    async function updateWindowInfo() {
        const e = document.getElementById('globalWindowInfo');
        if (!e) return;
        try {
            const w = await getJSON(withSeason('/api/time-window'));
            e.textContent = w.has_window ? `${w.start_label}
-> ${w.end_label}` : ''
        }
        catch (_) { e.textContent = '' }
    }

    function fmt(v, d = 2) {
        if (v === null || v === undefined || v === '') return '-';
        if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(d);
        return String(v)
    }

    function roleClass(r) { return `role role-${String(r || 'x').toLowerCase()}` }
    function compareIds() { return JSON.parse(localStorage.getItem('fantastat.compareIds') || '[]') }
    function saveCompareIds(ids) {
        const clean = [...new Set(ids.filter(Boolean).map(String))].slice(0, 6);
        localStorage.setItem('fantastat.compareIds', JSON.stringify(clean));
        updateCompareNav();
        return clean
    }

    function addCompare(id) {
        const ids = compareIds();
        if (!ids.includes(String(id))) ids.push(String(id));
        return saveCompareIds(ids)
    }

    function clearCompare() { return saveCompareIds([]) }
    function compareUrl(ids = compareIds()) {
        const u = new URL('/compare', location.origin);
        ids.forEach(id => u.searchParams.append('id', id));
        if (selectedSeason()) u.searchParams.set('season', selectedSeason());
        if (selectedDays()) u.searchParams.set('days', selectedDays());
        return u.pathname + u.search
    }

    function updateCompareNav() {
        const n = document.getElementById('navCompare');
        if (n) n.href = compareUrl()
    }

    function toast(m) {
        const e = document.getElementById('toast');
        if (!e) return;
        e.textContent = m;
        e.classList.remove('hidden');
        setTimeout(() => e.classList.add('hidden'), 2200)
    }

    function chartLine(ctx, labels, datasets) {
        return new Chart(ctx, {
            type: 'line', data: { labels, datasets }, options: {
                responsive: true, tension: .25, spanGaps: true, plugins: {
                    legend: {
                        labels: { color: '#dbeafe' }
                    }
                }, scales: {
                    x: {
                        ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' }
                    }, y: {
                        ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,.12)' }
                    }
                }
            }
        })
    }
    return {
        getJSON, withSeason, initSeasonSelector, selectedSeason, selectedDays, fmt, roleClass, addCompare, clearCompare, compareIds, compareUrl, updateCompareNav, toast, chartLine
    }
})();

