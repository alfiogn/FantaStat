# Fantacalcio Scraped Data Structure

Purpose: make the scraped data structure explicit and easy for an LLM to consume when generating Python code.

This document describes the objects produced by the scraper:

```text
quotazioni<year>.csv      # flat table, one row per player
stats<year>.json          # dictionary-like cache, one key per player
stats[player_name]        # player-level historical dataframe payload
```

Assumption: the scraper source is the current `scraper.py`. In the refactored version, the same logical structure is preserved, but `pandas.DataFrame` objects are serialised to JSON as `{records, attrs}`.

---

## 1. Top-level data model

The scraper produces two main datasets.

```python
quotazioni: pandas.DataFrame
stats: dict[str, pandas.DataFrame]
```

Conceptually:

```python
{
    "quotazioni": DataFrame[one row per player],
    "stats": {
        "PLAYER_NAME": DataFrame[one row per matchweek],
        ...
    }
}
```

When cached to disk:

```text
cache/
  quotazioni2026.csv
  stats2026.json
```

For year `2026`, the corresponding Fantacalcio season URL is:

```text
https://www.fantacalcio.it/quotazioni-fantacalcio/2025-26
```

Mapping rule:

```python
reference_year = 2026
season = f"{reference_year - 1}-{str(reference_year)[-2:]}"
# "2025-26"
```

---

## 2. `quotazioni<year>.csv`

### 2.1 Meaning

Flat player registry extracted from the Fantacalcio quotation table.

One row corresponds to one player.

### 2.2 Columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `url` | string | yes | Player detail page URL. Used to scrape historical stats. |
| `nome` | string | no | Player name as shown in the quotation table. Used as the key in `stats`. |
| `ruolo` | string | yes | Classic role. Expected values are usually `P`, `D`, `C`, `A`. |
| `squadra` | string | yes | Real Serie A team. |
| `QI` | integer | yes | Initial classic quotation. |
| `QA` | integer | yes | Current classic quotation. |
| `FVM` | integer | yes | Fantacalcio market value from the quotation table. |

### 2.3 Example row

```json
{
  "url": "https://www.fantacalcio.it/squadre/inter/lautaro-martinez/1234",
  "nome": "Lautaro Martinez",
  "ruolo": "A",
  "squadra": "Inter",
  "QI": 42,
  "QA": 45,
  "FVM": 53
}
```

### 2.4 Typical usage

```python
import pandas as pd

quotazioni = pd.read_csv("cache/quotazioni2026.csv")

attackers = quotazioni[quotazioni["ruolo"] == "A"]
top_fvm = attackers.sort_values("FVM", ascending=False).head(20)
```

---

## 3. `stats` object in memory

### 3.1 Meaning

Dictionary indexed by player name.

```python
stats: dict[str, pandas.DataFrame]
```

Each value is a `pandas.DataFrame` with:

```text
one row per matchweek / giornata
plus metadata stored in df.attrs
```

Example:

```python
player_df = stats["Lautaro Martinez"]
player_df              # matchweek-level time series
player_df.attrs        # player metadata, summaries, graph metadata
```

---

## 4. `stats<year>.json` serialised structure

A `pandas.DataFrame` cannot be stored directly in JSON. The robust representation is:

```json
{
  "PLAYER_NAME": {
    "records": [
      {"giornata": 1, "voto": 6.5, "fantavoto": 10.5},
      {"giornata": 2, "voto": 6.0, "fantavoto": 6.0}
    ],
    "attrs": {
      "player_name": "PLAYER_NAME",
      "team": "Inter"
    }
  }
}
```

Recommended deserialiser:

```python
import json
import pandas as pd

with open("cache/stats2026.json", encoding="utf-8") as f:
    payload = json.load(f)

stats = {}
for name, player_payload in payload.items():
    df = pd.DataFrame(player_payload.get("records", []))
    df.attrs.update(player_payload.get("attrs", {}))
    stats[name] = df
```

Recommended serialiser:

```python
def dataframe_to_payload(df: pd.DataFrame) -> dict:
    return {
        "records": df.to_dict(orient="records"),
        "attrs": dict(df.attrs),
    }

payload = {name: dataframe_to_payload(df) for name, df in stats.items()}
```

---

## 5. Player historical dataframe: `stats[player_name]`

### 5.1 Meaning

A single player's historical matchweek data.

Each row corresponds to one `giornata`.

### 5.2 Core columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `giornata` | integer | no | Matchweek number. Primary time index. |
| `status` | string | yes | Text status for the matchweek, e.g. started, substituted, unused, injured, suspended. Exact values depend on source text. |
| `status_code` | integer/float/string | yes | Numeric/source status code from visual component attributes. |
| `match_url` | string | yes | URL of the match detail page. |
| `match_text` | string | yes | Raw compact text of the match link. |
| `team_home` | string | yes | Home team. |
| `team_away` | string | yes | Away team. |
| `score_home` | integer | yes | Home score. |
| `score_away` | integer | yes | Away score. |
| `active_team` | string | yes | Team associated with the active player row. |
| `win` | integer | yes | `1` win, `0` draw, `-1` loss, `None` if score cannot be parsed. |

### 5.3 Vote and fantasy vote columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `voto` | float | yes | Table vote. |
| `fantavoto` | float | yes | Table fantasy vote. |
| `voto_graph` | float | yes | Vote extracted from the graph data. |
| `fantavoto_graph` | float | yes | Fantasy vote extracted from the graph data. |

Notes:

- `voto` and `fantavoto` come from the season table.
- `voto_graph` and `fantavoto_graph` come from graph attributes.
- They may differ if the website exposes missing/invalid graph values differently from the table.

### 5.4 Substitution columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `sub_in_minute` | integer/float | yes | Minute of substitution in. |
| `sub_out_minute` | integer/float | yes | Minute of substitution out. |

### 5.5 Bonus, malus and price graph columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `bonus_graph` | float | yes | Bonus value from bonus/malus graph. |
| `malus_graph` | float | yes | Malus value from bonus/malus graph. |
| `quotazione_classic` | float | yes | Classic quotation at this matchweek. |
| `quotazione_mantra` | float | yes | Mantra quotation at this matchweek. |

### 5.6 Event columns

| Column | Type | Nullable | Meaning |
|---|---:|---:|---|
| `events` | list[dict] | no | Raw event objects extracted from bonus icons. |
| `event_counts` | dict[str, number] | no | Aggregated event counts by event key. |
| `assists` | number | no | Count/value of assists. Defaults to `0`. |
| `scoredGoals` | number | no | Count/value of scored goals. Defaults to `0`. |
| `yellowCards` | number | no | Count/value of yellow cards. Defaults to `0`. |
| `redCards` | number | no | Count/value of red cards. Defaults to `0`. |
| `ownGoals` | number | no | Count/value of own goals. Defaults to `0`. |

Example `events` value:

```json
[
  {
    "key": "scoredGoals",
    "title": "Gol segnato",
    "value": 1,
    "attrs": {
      "data-key": "scoredGoals",
      "data-value": "1",
      "title": "Gol segnato"
    }
  }
]
```

Example `event_counts` value:

```json
{
  "scoredGoals": 1,
  "assists": 1
}
```

### 5.7 Raw/debug columns

These preserve source HTML attributes. They are useful for debugging, reverse engineering and future extraction logic.

| Column | Type | Meaning |
|---|---:|---|
| `row_attrs` | dict | Attributes of the source table row. |
| `matchweek_attrs` | dict | Attributes of the matchweek cell/component. |
| `match_attrs` | dict | Attributes of the match link. |
| `grade_attrs` | dict | Attributes of the vote element. |
| `fanta_grade_attrs` | dict | Attributes of the fantasy vote element. |
| `sub_in_attrs` | dict | Attributes of the substitution-in element. |
| `sub_out_attrs` | dict | Attributes of the substitution-out element. |
| `status_stripe_attrs` | dict | Attributes of the visual status stripe for the giornata. |
| `grade_graph_attrs` | dict | Full graph record for vote/fantasy vote at this giornata. |
| `bonus_malus_graph_attrs` | dict | Full graph record for bonus/malus at this giornata. |
| `price_graph_attrs` | dict | Full graph record for quotation at this giornata. |
| `raw_row_html` | string | Raw HTML of the matchweek table row. Heavy, optional for downstream processing. |

Recommendation: exclude `raw_row_html` before feeding data to an LLM unless HTML-level debugging is required.

---

## 6. Player dataframe metadata: `df.attrs`

Each `stats[player_name]` dataframe has metadata stored in `df.attrs`.

This is not row-level data. It describes the player and source page.

### 6.1 Top-level attrs keys

```python
df.attrs.keys()
```

Expected keys:

| Key | Type | Meaning |
|---|---:|---|
| `source_url` | string | URL used to scrape the player page. |
| `page_title` | string | HTML page title. |
| `canonical_url` | string | Canonical page URL. |
| `og_url` | string | OpenGraph URL. |
| `og_image` | string | OpenGraph image URL. |
| `meta_description` | string | HTML meta description. |
| `player_name` | string | Player name from detail page. |
| `team` | string | Team from detail page. |
| `team_url` | string | Team page URL. |
| `birthdate_iso` | string | Birthdate from structured metadata, if available. |
| `image` | string | Player image URL, if available. |
| `description` | string | Textual player description. |
| `roles` | list[dict] | Role pills from detail page. |
| `player_data` | dict | Player biographical/details section. |
| `top_stats` | dict | Highlight stats displayed near the top of the page. |
| `summary_stats` | dict | Summary statistics from the player page. |
| `dataset_stats` | list[dict] | Dataset-level stat records. |
| `season_status_percent` | list[dict] | Status percentage breakdown. |
| `download_player_detail_href` | string | Download link if exposed. |
| `bridge` | dict | Parsed JavaScript `Bridge` object fields. |
| `graphs` | dict | Metadata for grades, bonuses and price graphs. |
| `preseason_price` | dict | Price graph record at x/giornata `0`, if available. |

---

## 7. Nested metadata structures

### 7.1 `roles`

```json
[
  {
    "data_value": "A",
    "title": "Attaccante",
    "attrs": {
      "class": "role",
      "data-value": "A",
      "title": "Attaccante"
    }
  }
]
```

### 7.2 `player_data`

Dictionary keyed by source labels.

Example:

```json
{
  "Data di nascita": {
    "text": "22/08/1997",
    "attrs": {}
  },
  "Altezza": {
    "text": "174 cm",
    "attrs": {}
  }
}
```

Labels are source-dependent. Code should not assume that every player has the same keys.

### 7.3 `top_stats`

Dictionary keyed by group name.

Example structure:

```json
{
  "Statistiche": [
    {
      "title": "Gol",
      "value": 12,
      "label": "G",
      "li_attrs": {}
    }
  ]
}
```

### 7.4 `summary_stats`

Dictionary keyed by stat name.

Each record has:

```json
{
  "name": "MV",
  "value": 6.42,
  "attrs": {}
}
```

Typical keys may include media voto, fantamedia and other source-defined summary metrics. Do not hard-code the full set without checking the payload.

### 7.5 `dataset_stats`

List of records:

```json
[
  {
    "name": "MV",
    "value": 6.42,
    "attrs": {}
  }
]
```

### 7.6 `season_status_percent`

List of records:

```json
[
  {
    "name": "Titolare",
    "value": "52%",
    "attrs": {}
  }
]
```

The value may be a string containing `%`. Convert explicitly if numerical analysis is needed.

### 7.7 `bridge`

Dictionary parsed from the page JavaScript block named `Bridge`.

Possible fields include:

```json
{
  "playerId": 1234,
  "playerPosition": "A",
  "playerName": "Lautaro Martinez",
  "teamName": "Inter",
  "season": "2025-26"
}
```

The set of fields is source-dependent.

---

## 8. Graph structures

The scraper extracts three graph sections:

```python
grade_graph = _graph_series(soup, "player-grades-graph")
bonus_graph = _graph_series(soup, "player-bonuses-graph")
price_graph = _graph_series(soup, "player-price-graph")
```

These are used both to add row-level columns and to populate metadata.

### 8.1 Generic graph payload

```json
{
  "meta": {
    "section_id": "player-price-graph",
    "section_title": "Quotazioni",
    "legend": ["Classic", "Mantra"],
    "frame_attrs": {},
    "items_attrs": {}
  },
  "data": {
    "1": {
      "primary": 42,
      "secondary": 44,
      "tertiary": null,
      "x_axis_attrs": {},
      "item_attrs": {},
      "primary_item_value": 42,
      "secondary_item_value": 44,
      "tertiary_item_value": null,
      "primary_item_attrs": {},
      "secondary_item_attrs": {},
      "tertiary_item_attrs": {}
    }
  }
}
```

### 8.2 Interpretation by section

| Section id | Row-level columns | Interpretation |
|---|---|---|
| `player-grades-graph` | `voto_graph`, `fantavoto_graph` | `primary = voto`, `secondary = fantavoto`. |
| `player-bonuses-graph` | `bonus_graph`, `malus_graph` | `primary = bonus`, `secondary = malus`. |
| `player-price-graph` | `quotazione_classic`, `quotazione_mantra` | `primary = classic quotation`, `secondary = mantra quotation`. |

### 8.3 `df.attrs["graphs"]`

Only graph metadata is stored in `df.attrs["graphs"]`:

```json
{
  "grades": {"section_id": "player-grades-graph", "legend": ["Voto", "FantaVoto"]},
  "bonuses": {"section_id": "player-bonuses-graph", "legend": ["Bonus", "Malus"]},
  "prices": {"section_id": "player-price-graph", "legend": ["Classic", "Mantra"]}
}
```

The full per-giornata graph records are stored in dataframe columns:

```text
grade_graph_attrs
bonus_malus_graph_attrs
price_graph_attrs
```

---

## 9. Recommended LLM-facing compact schema

When asking an LLM to generate code, provide this compact schema instead of the full raw scrape.

```yaml
quotazioni:
  type: pandas.DataFrame
  grain: one row per player
  key: nome
  columns:
    url: string, player detail URL
    nome: string, player name
    ruolo: string, one of P/D/C/A when available
    squadra: string, real team
    QI: numeric, initial quotation
    QA: numeric, current quotation
    FVM: numeric, market value

stats:
  type: dict[str, pandas.DataFrame]
  key: player name, matching quotazioni.nome
  value_grain: one row per player per giornata
  dataframe_required_columns:
    giornata: integer time index
  dataframe_common_columns:
    status: string
    status_code: numeric/string
    match_url: string
    match_text: string
    team_home: string
    team_away: string
    score_home: integer
    score_away: integer
    active_team: string
    win: integer, 1 win, 0 draw, -1 loss
    voto: numeric
    fantavoto: numeric
    voto_graph: numeric
    fantavoto_graph: numeric
    sub_in_minute: numeric
    sub_out_minute: numeric
    bonus_graph: numeric
    malus_graph: numeric
    quotazione_classic: numeric
    quotazione_mantra: numeric
    events: list[dict]
    event_counts: dict[str, number]
    assists: number
    scoredGoals: number
    yellowCards: number
    redCards: number
    ownGoals: number
    is_placeholder: boolean
    match_date: ISO date string
    match_time: string
    stadium: string
    calendar_match_status: numeric/string
  attrs:
    player_name: string
    team: string
    roles: list[dict]
    summary_stats: dict[str, {name, value, attrs}]
    dataset_stats: list[{name, value, attrs}]
    season_status_percent: list[{name, value, attrs}]
    bridge: dict
    graphs: dict
    preseason_price: dict
    calendar_season: string
    calendar_placeholders_added: integer
```

---

## 10. Common derived tables

### 10.1 Player summary table

Useful for dashboard, ranking and auction support.

```python
rows = []

for name, df in stats.items():
    rows.append({
        "nome": name,
        "partite": len(df),
        "voto_mean": pd.to_numeric(df.get("voto"), errors="coerce").mean(),
        "fantavoto_mean": pd.to_numeric(df.get("fantavoto"), errors="coerce").mean(),
        "goal": pd.to_numeric(df.get("scoredGoals"), errors="coerce").sum(),
        "assist": pd.to_numeric(df.get("assists"), errors="coerce").sum(),
        "yellow": pd.to_numeric(df.get("yellowCards"), errors="coerce").sum(),
        "red": pd.to_numeric(df.get("redCards"), errors="coerce").sum(),
        "team_detail": df.attrs.get("team"),
    })

summary = pd.DataFrame(rows)
players = quotazioni.merge(summary, on="nome", how="left")
```

### 10.2 Long time-series table

Useful for plotting and modelling.

```python
frames = []

for name, df in stats.items():
    tmp = df.copy()
    tmp["nome"] = name
    tmp["real_team"] = df.attrs.get("team")
    frames.append(tmp)

all_matchweeks = pd.concat(frames, ignore_index=True)
```

Resulting grain:

```text
one row per player per giornata
```

### 10.3 Player comparison table

```python
def compare_players(stats, players, metric):
    frames = []
    for player in players:
        df = stats[player]
        tmp = df[["giornata", metric]].copy()
        tmp[metric] = pd.to_numeric(tmp[metric], errors="coerce")
        tmp["player"] = player
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True)
```

---

## 11. Data quality and defensive coding notes

### 11.1 Missing values

Expect missing values in:

```text
voto
fantavoto
score_home
score_away
sub_in_minute
sub_out_minute
quotazione_classic
quotazione_mantra
```

Use:

```python
pd.to_numeric(series, errors="coerce")
```

### 11.2 Dict and list columns

Some dataframe columns are nested:

```text
events
event_counts
row_attrs
match_attrs
grade_graph_attrs
bonus_malus_graph_attrs
price_graph_attrs
```

These are useful for debugging, but inconvenient for tabular ML. Flatten or drop them.

### 11.3 Player name as key

`stats` is keyed by `nome`. This is convenient but not guaranteed to be globally unique across all seasons or all competitions.

If available, prefer `df.attrs["bridge"]["playerId"]` as a stable identifier.

Recommended robust key:

```python
player_id = df.attrs.get("bridge", {}).get("playerId")
```

Fallback:

```python
key = (nome, squadra, ruolo)
```

### 11.4 Raw HTML

`raw_row_html` can make JSON large. Drop it for LLM prompts and dashboards if not needed.

```python
for df in stats.values():
    if "raw_row_html" in df.columns:
        df = df.drop(columns=["raw_row_html"])
```

### 11.5 Graph keys in JSON

In memory, graph `data` keys can be numeric integers like `1`, `2`, `3`.

In JSON, object keys become strings:

```json
{
  "1": {...},
  "2": {...}
}
```

Convert back if needed:

```python
graph_data = {int(k): v for k, v in graph_data.items()}
```

---

## 12. Recommended prompt block for an LLM

Use this block when asking an LLM to generate Python code over the data.

```text
I have Fantacalcio scraped data with two cached files:

1. cache/quotazioni2026.csv
   - pandas DataFrame grain: one row per player
   - columns: url, nome, ruolo, squadra, QI, QA, FVM
   - nome is the join key to player stats

2. cache/stats2026.json
   - JSON object keyed by player name
   - each value is {records: list[dict], attrs: dict}
   - records reconstruct a pandas DataFrame with grain one row per player per giornata
   - attrs are the original dataframe metadata

Each player dataframe commonly has:
- giornata
- status, status_code
- match_url, match_text
- team_home, team_away, score_home, score_away, active_team, win
- voto, fantavoto, voto_graph, fantavoto_graph
- sub_in_minute, sub_out_minute
- bonus_graph, malus_graph
- quotazione_classic, quotazione_mantra
- events, event_counts
- assists, scoredGoals, yellowCards, redCards, ownGoals
- raw/debug attrs columns such as row_attrs, match_attrs, graph attrs and raw_row_html

Each player dataframe attrs commonly has:
- player_name, team, roles, player_data
- top_stats, summary_stats, dataset_stats
- season_status_percent
- bridge, graphs, preseason_price

Write robust pandas code. Do not assume every column exists. Use pd.to_numeric(..., errors="coerce") for numeric metrics. Avoid using raw_row_html unless required.
```
