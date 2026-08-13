# Phase 2 Backend Implementation

This package implements the backend layer for the Fantastat web app.

## Included

- MongoDB connection wrapper
- Repositories
- Services
- Page routes
- API routes
- Minimal placeholder templates for runnable Flask startup

## Run

```bash
pip install -r requirements.txt
python app.py
```

Default database settings:

```text
FANTASTAT_MONGO_URI=mongodb://localhost:27017
FANTASTAT_MONGO_DATABASE=fantastat
```

## API

```text
/api/seasons
/api/quotations
/api/filters
/api/player/<player_id>
/api/player/<player_id>/timeline
/api/compare?id=<id>&id=<id>
/api/teams
/api/team/<team_code>/fixtures
/api/matchday/<matchday>
/api/season-status
```

## Notes

- Routes do not access MongoDB directly.
- Templates do not access MongoDB directly.
- All reads go through repositories.
- Services return frontend-ready payloads.
- Current season partial data is treated as normal.
