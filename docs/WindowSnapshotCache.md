# Window Snapshot Cache

This patch introduces an in-memory cache for rolling-window statistics.

## Why

Before the patch, every request to `/api/quotations`, `/api/player/<id>` and `/api/compare` recomputed rolling-window records and metrics.

That is expensive because `/api/quotations` touches every player.

## New service

```text
web/services/window_snapshot.py
```

Main class:

```python
WindowSnapshotService
```

Cache key:

```python
(season, days)
```

Cached payload:

```python
WindowSnapshot(
    season,
    days,
    window,
    rows,
    by_player_id,
    timelines,
    records,
)
```

## API changes

The following endpoints now reuse the same cached snapshot:

```text
/api/quotations
/api/player/<player_id>
/api/player/<player_id>/timeline
/api/compare
```

## New diagnostics endpoints

```text
GET  /api/cache/window
POST /api/cache/clear
```

Use `/api/cache/window` to inspect cache entries.
Use `/api/cache/clear` after a fresh scrape/builddb if the Flask process stays alive.

## Default cache policy

```python
ttl_seconds = 900
max_entries = 32
```

So snapshots live for 15 minutes and at most 32 `(season, days)` combinations are kept.

## Integration

In `routes/context.py`, add:

```python
from services.window_snapshot import WindowSnapshotService

window_snapshot_service = WindowSnapshotService(
    quotation_repo=quotation_repo,
    player_repo=player_repo,
    time_window_service=time_window_service,
    timeline_service=timeline_service,
    ttl_seconds=900,
    max_entries=32,
)
```

Then replace `routes/api.py` with the provided cached version.
