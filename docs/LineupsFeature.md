# Lineups Feature

Adds a new dashboard page:

```text
/lineups
```

The page renders interactive pitch infographics from the parsed Fantacalcio article HTML.

## Data source

- `web/data/info.html` is the saved article body.
- `web/static/data/lineups_2027.json` is the generated JSON used by the browser.

The parser extracts:

- team
- coach
- module
- starting XI
- ballottaggi
- rigoristi
- calci da fermo

## Player actions

Each pitch player has:

- Open
- Compare

The frontend matches article player names against `/api/quotations` rows for the selected season.

If no Mongo match is found, a toast is shown.

## Copyright note

This implementation does not copy Fantacalcio image assets. It recreates the tactical layout with CSS and text-only player markers. That avoids depending on external image URLs and keeps the page local.
