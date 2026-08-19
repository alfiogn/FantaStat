# Rolling Last N Fantasy Days Across Seasons

The topbar label says `Last days`, but the unit is Fantacalcio/Serie A giornata.

## Correct current-season rule

A current season contributes matchdays only when those matchdays are actually meaningful, meaning the calendar has at least one fixture with:

```text
calendar_match_status = FINISHED
```

Calendar-only future matchdays do **not** count.

## Example before the new season starts

If today the selected season is `2027`, but no 2027 match has been played yet:

```text
latest meaningful matchday in 2027 = None
Last days = 38
```

The rolling window is:

```text
2026 MD1..MD38
```

## Example after 2027 MD1 is played

If one 2027 matchday has been played:

```text
latest meaningful matchday in 2027 = 1
Last days = 38
```

The rolling window is:

```text
2026 MD2..MD38
+
2027 MD1
```

## Example after 2027 MD10 is played

```text
latest meaningful matchday in 2027 = 10
Last days = 38
```

The rolling window is:

```text
2026 MD11..MD38
+
2027 MD1..MD10
```

## Metrics computed over the rolling window

- `window_QI`: first `quotazione_classic` found in the window, fallback to selected-season QI
- `window_QA`: last `quotazione_classic` found in the window, fallback to selected-season QA
- `window_quotation_delta`
- `window_FV`: average `fantavoto`
- `window_MV`: average `voto`
- `window_FVM`: current selected-season quotation snapshot FVM
- `window_goals`
- `window_assists`

`FVM` is not historical in the scraped player records, so `window_FVM` uses the quotation snapshot of the selected season.
