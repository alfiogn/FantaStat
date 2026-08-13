# Phase 4: Current-Season Handling

Phase 4 adds explicit support for seasons where the calendar is complete but player timelines are partial.

## Backend additions

New API endpoints:

```text
/api/season-status
/api/player/<player_id>/season-status
/api/player/<player_id>/fixtures
```

## Behavior

A season is partial when:

- calendar matchdays exist beyond the last available player timeline matchday, or
- no player timeline data exists yet while quotations/calendar already exist.

This is not an error. The web app displays a status banner and uses future calendar rows as fixtures.

## Player page

The player page now shows:

- current-season status banner
- last known player matchday
- total calendar matchdays
- next fixtures from the calendar

## Dashboard

The dashboard now shows a season status banner.

## Team matching

Calendar team names can be full names while quotations use short codes. The calendar repository now includes common Serie A aliases such as:

```text
INT -> Inter, Internazionale
ROM -> Roma
NAP -> Napoli
MIL -> Milan
JUV -> Juventus
```

This allows player future fixtures to work even when player documents store the team as a short code.
