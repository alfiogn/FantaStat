# Global Last N Days Design

This replaces the previous table-only last-N filter.

## Location

The control belongs in the top bar next to the season selector:

```html
<select id="globalSeason"></select>
<input id="globalDays" value="38">
```

## Semantics

`N` is calendar days, not matchdays.

The backend computes:

```text
anchor_date = most recent FINISHED calendar match date
start_date = anchor_date - N days
end_date = anchor_date
```

All dashboard, player and comparison statistics are recomputed from records whose `match_date` falls inside:

```text
[start_date, end_date]
```

## Metrics

For each player row:

```text
window_QI              first quotazione_classic in the window, fallback QI
window_QA              last quotazione_classic in the window, fallback QA
window_quotation_delta window_QA - window_QI
window_FV              average fantavoto in the window
window_MV              average voto in the window
window_FVM             FVM from quotation snapshot
window_goals           goals in the window
window_assists         assists in the window
```

## Note on FVM

The scraped data does not contain a historical FVM time series. Therefore `window_FVM` is the FVM from the current quotation snapshot unless Builder is extended later to store FVM history.
