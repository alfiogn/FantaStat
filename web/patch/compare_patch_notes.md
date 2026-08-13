# Compare changes

`Fantastat.withSeason()` now injects both `season` and `days`, so comparison calls automatically use the global date window.

In `compare.js`, make sure the API URL includes:

```javascript
params.set('days', Fantastat.selectedDays());
```

The comparison service should use `time_window_service.window_records(player_id, season, days)` instead of full-season records.
