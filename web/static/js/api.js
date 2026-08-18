'use strict';

window.Fantastat = (() => {
    let pendingRequests = 0;
    let spinnerTimer = null;

    function showLoader() {
        pendingRequests++;

        if (spinnerTimer === null) {
            spinnerTimer = setTimeout(() => {
                spinnerTimer = null;

                if (pendingRequests > 0) {
                    document
                        .getElementById("loadingOverlay")
                        ?.classList.remove("hidden");
                }
            }, 150);
        }
    }

    function hideLoader() {
        pendingRequests--;

        if (pendingRequests <= 0) {
            pendingRequests = 0;

            if (spinnerTimer !== null) {
                clearTimeout(spinnerTimer);
                spinnerTimer = null;
            }

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
        const clean =
            [...new Set(ids.filter(Boolean).map(String))]
                .slice(0, 80);

        localStorage.setItem(
            'fantastat.compareIds',
            JSON.stringify(clean)
        );

        updateCompareNav();

        return clean;
    }
    function addCompare(id) {
        const ids = compareIds();
        if (!ids.includes(String(id))) ids.push(String(id));
        return saveCompareIds(ids)
    }

    function clearCompare() { return saveCompareIds([]) }
    function removeCompare(id) {
        const ids = compareIds()
            .filter(existingId => String(existingId) !== String(id));

        return saveCompareIds(ids);
    }
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

    function renderBoxplot(containerId, title, box, options = {}) {
        const container = document.getElementById(containerId);

        if (!container) {
            return;
        }

        if (!box || !box.n) {
            container.innerHTML =
                `<div class="boxplot-empty">${title}: no data</div>`;
            return;
        }

        const minScale =
            options.min !== undefined ? options.min : box.min;

        const maxScale =
            options.max !== undefined ? options.max : box.max;

        const span =
            Math.max(maxScale - minScale, 1e-9);

        const x = value =>
            8 + 84 * ((value - minScale) / span);

        const min = x(box.min);
        const q1 = x(box.q1);
        const med = x(box.median);
        const q3 = x(box.q3);
        const max = x(box.max);
        const mean = x(box.mean);

        container.innerHTML = `
            <div class="boxplot-header">
                <strong>${title}</strong>
                <span>n=${box.n}</span>
            </div>

            <svg class="boxplot-svg" viewBox="0 0 100 42" preserveAspectRatio="none">
                <line class="boxplot-whisker" x1="${min}" y1="21" x2="${max}" y2="21"></line>

                <line class="boxplot-cap" x1="${min}" y1="13" x2="${min}" y2="29"></line>
                <line class="boxplot-cap" x1="${max}" y1="13" x2="${max}" y2="29"></line>

                <rect class="boxplot-box" x="${q1}" y="10" width="${Math.max(q3 - q1, 0.5)}" height="22"></rect>

                <line class="boxplot-median" x1="${med}" y1="8" x2="${med}" y2="34"></line>
                <circle class="boxplot-mean" cx="${mean}" cy="21" r="1.8"></circle>
            </svg>

            <div class="boxplot-values">
                <span>min ${Fantastat.fmt(box.min)}</span>
                <span>q1 ${Fantastat.fmt(box.q1)}</span>
                <span>med ${Fantastat.fmt(box.median)}</span>
                <span>q3 ${Fantastat.fmt(box.q3)}</span>
                <span>max ${Fantastat.fmt(box.max)}</span>
            </div>
        `;
    }

    return {
        getJSON,
        withSeason,
        initSeasonSelector,
        selectedSeason,
        selectedDays,
        fmt,
        roleClass,
        addCompare,
        removeCompare,
        clearCompare,
        compareIds,
        compareUrl,
        updateCompareNav,
        toast,
        chartLine,
        renderBoxplot
    }
})();

