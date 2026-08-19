# Fantastat Web Backend Contract

This document defines the service/repository contract for the Flask web application.

The web application must not access MongoDB directly from route functions or templates.
All MongoDB access must go through repositories.

## Repository layer

Required repositories:

```text
repositories/
  database.py
  quotation_repository.py
  player_repository.py
  calendar_repository.py
  team_repository.py
```

## QuotationRepository

### Methods

```python
seasons() -> list[int]
find_latest_season() -> int | None
list_quotations(season: int, role: str | None = None, team: str | None = None, search: str | None = None) -> list[dict]
get_player_quotation(season: int, player_id: int) -> dict | None
top_fvm(season: int, limit: int = 20) -> list[dict]
top_quotation(season: int, limit: int = 20) -> list[dict]
```

### Collection used

```text
quotation_rows
```

## PlayerRepository

### Methods

```python
get_player(player_id: int | str) -> dict | None
get_player_by_name(name: str) -> dict | None
search_players(query: str, season: int | None = None, limit: int = 20) -> list[dict]
get_player_season(player_id: int | str, season: int) -> dict | None
get_player_records(player_id: int | str, season: int) -> list[dict]
```

### Collection used

```text
players
```

## CalendarRepository

### Methods

```python
list_matchdays(season: int) -> list[int]
get_matchday(season: int, matchday: int) -> list[dict]
team_fixtures(season: int, team: str) -> list[dict]
next_team_fixtures(season: int, team: str, after_matchday: int, limit: int = 5) -> list[dict]
```

### Collection used

```text
calendar_matches
```

## TeamRepository

### Methods

```python
list_teams(season: int) -> list[dict]
get_team(season: int, team_code: str) -> dict | None
```

### Collection used

```text
teams
```

## Service layer

Required services:

```text
services/
  summaries.py
  timeline.py
  comparison.py
  current_season.py
```

## TimelineService

Builds chart-ready time series from `players.seasons.<season>.records`.

### Output shape

```json
{
  "matchdays": [1, 2, 3],
  "voto": [6.0, 6.5, null],
  "fantavoto": [6.0, 10.0, null],
  "quotation": [25, 27, 27],
  "goals_cumulative": [0, 1, 1],
  "assists_cumulative": [0, 0, 1]
}
```

## ComparisonService

Compares two or more players for one season.

### Output shape

```json
{
  "season": 2027,
  "players": [
    {
      "player_id": 2764,
      "name": "Martinez L.",
      "summary": {},
      "timeline": {}
    }
  ],
  "metrics": [
    "current_price",
    "fvm",
    "avg_fantavote",
    "goals",
    "assists",
    "appearances"
  ]
}
```

## CurrentSeasonService

Detects incomplete seasons without throwing errors.

### Output shape

```json
{
  "season": 2027,
  "last_calendar_matchday": 38,
  "last_known_player_matchday": 2,
  "is_partial": true,
  "available_player_matchdays": [1, 2],
  "calendar_matchdays": [1, 2, 3, 4, 5]
}
```

## Route contract

Required page routes:

```text
/                         dashboard
/player/<player_id>       player page
/compare                  comparison page
/team/<team_code>         team page
/matchday/<int:matchday>  matchday page
```

Required API routes:

```text
/api/seasons
/api/quotations
/api/player/<player_id>
/api/player/<player_id>/timeline
/api/compare
/api/teams
/api/team/<team_code>/fixtures
/api/matchday/<matchday>
```

## Frontend rule

Frontend JavaScript must only call API routes.
It must never embed Mongo-specific assumptions beyond field names returned by the backend.

