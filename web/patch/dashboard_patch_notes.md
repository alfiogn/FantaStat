# Dashboard changes

Use the global `days` parameter. Remove page-local `lastNInput`.

In `loadQuotations()` send no explicit table-only last-N value. `Fantastat.withSeason()` now injects `days` globally.

Add columns based on window metrics:

```javascript
r.window_QI
r.window_FV
r.window_FVM
r.window_goals
r.window_assists
```

Recommended table columns after the static quote columns:

```html
<th class="num">W QI</th>
<th class="num">W FV</th>
<th class="num">W FVM</th>
<th class="num">W G</th>
<th class="num">W A</th>
```

`W` means global date window.
