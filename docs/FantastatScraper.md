# Scraping Logic

`scraper.py` produces three persistent artefacts:

```text
calendarYYYY.json
quotazioniYYYY.csv
statsYYYY.json
```

Data is collected from two independent providers:

| Source | Purpose |
|----------|----------|
| Lega Serie A SDP API | Official fixtures, match dates, matchday numbering, scores, stadiums, team identities |
| Fantacalcio | Player registry, quotations, player match reports, votes, fantavotes, events, market values |

The scraping workflow is:

1. Resolve season from reference year.
2. Download complete Serie A fixture list.
3. Save season calendar.
4. Download Fantacalcio quotations table.
5. Save quotations CSV.
6. Create one player timeline per quoted player.
7. Download each player's Fantacalcio page.
8. Extract seasonal metadata.
9. Extract player timeline records.
10. Merge player records with official calendar records.
11. Validate timeline continuity.
12. Save stats database.

Important design principle:

> Calendar data defines match existence.  
> Fantacalcio data enriches matches with player-level statistics.

Therefore:

- fixtures originate from Lega Serie A
- votes originate from Fantacalcio
- quotations originate from Fantacalcio
- scores originate from Lega Serie A
- stadiums originate from Lega Serie A

---

# calendarYYYY.json

## Data source

Lega Serie A SDP API:

```text
GET /seasons/{seasonId}/matches
```

The calendar file contains the complete Serie A schedule for a season.

Every match is stored exactly once.

---

## Top-level structure

```json
{
    "records": [
        {...},
        {...}
    ]
}
```

`records` is a list containing all Serie A fixtures.

Typical season:

```text
380 matches
38 matchdays
20 teams
```

---

## Match record structure

Each element of `records` represents a single Serie A match.

```json
{
    "giornata": 1,
    "match_text": "Internazionale - Torino",
    "team_home": "Internazionale",
    "team_away": "Torino",
    "score_home": 5,
    "score_away": 0,
    "match_date": "2025-08-25T18:45:00Z",
    "stadium": "Giuseppe Meazza",
    "calendar_match_status": "FINISHED",
    "raw_serie_a_match": {...}
}
```

---

## Important numerical fields

### giornata

Serie A matchday.

```json
"giornata": 1
```

Range:

```text
1-38
```

Primary timeline index.

---

### score_home

Goals scored by home team.

```json
"score_home": 5
```

---

### score_away

Goals scored by away team.

```json
"score_away": 0
```

---

### win information

Can be inferred as:

```python
if score_home > score_away:
    home_win = 1

if score_home == score_away:
    draw = 1

if score_home < score_away:
    away_win = 1
```

---

## Team fields

### team_home

Home team name.

```json
"team_home": "Internazionale"
```

### team_away

Away team name.

```json
"team_away": "Torino"
```

---

## Date fields

### match_date

Official UTC kickoff timestamp.

```json
"match_date": "2025-08-25T18:45:00Z"
```

---

### stadium

Official stadium name.

```json
"stadium": "Giuseppe Meazza"
```

---

## Match state fields

### calendar_match_status

Observed values:

```text
FINISHED
LIVE
UPCOMING
POSTPONED
```

Example:

```json
"calendar_match_status": "FINISHED"
```

---

## raw_serie_a_match

Unmodified Lega Serie A response.

Contains:

```json
{
    "matchId": "...",
    "providerId": "...",
    "status": "...",
    "phase": "...",
    "home": {...},
    "away": {...},
    "matchSet": {...},
    "providerHomeScore": ...,
    "providerAwayScore": ...
}
```

Useful for:

- debugging
- future schema evolution
- retrieving hidden metadata
- obtaining official team identifiers

Not required by downstream analytics.

---

# quotazioniYYYY.csv

## Data source

Fantacalcio Quotazioni page.

Contains the complete player registry for the season.

One row corresponds to one player.

---

## CSV structure

```csv
url,team_slug,nome,ruolo,squadra,QI,QA,FVM
```

---

## Column descriptions

### url

Canonical Fantacalcio player page.

Example:

```text
https://www.fantacalcio.it/serie-a/squadre/inter/martinez-l/2764/2025-26
```

Contains:

- team slug
- Fantacalcio player id
- season

---

### team_slug

Team slug used by Fantacalcio URLs.

Example:

```csv
inter
napoli
roma
```

---

### nome

Player display name.

Example:

```csv
Martinez L.
Calhanoglu
Lukaku
```

---

### ruolo

Fantacalcio role.

Values:

```text
P = Goalkeeper
D = Defender
C = Midfielder
A = Forward
```

---

### squadra

Three-letter team code.

Examples:

```text
INT
JUV
NAP
ROM
MIL
```

---

### QI

Initial quotation.

Player price at season start.

Example:

```csv
34
```

---

### QA

Current quotation.

Player price at scraping date.

Example:

```csv
33
```

---

### FVM

Fantavalore di Mercato.

Highest-value numerical indicator provided by Fantacalcio.

Example:

```csv
315
```

Used extensively for:

- rankings
- player valuation
- transfer suggestions

---

## Useful derived quantities

### Player Id

Extracted from:

```text
.../martinez-l/2764/2025-26
```

Result:

```json
{
    "player_id": 2764
}
```

---

### Quotation delta

```python
QA - QI
```

Example:

```python
33 - 34 = -1
```

---

### Quotation growth %

```python
(QA - QI)/QI*100
```

---

# statsYYYY.json

## Data source

Fantacalcio player detail pages merged with official Serie A calendar.

This is the main database generated by the scraper.

---

## Top-level structure

```json
{
    "Martinez L.": {
        "records": [...],
        "attrs": {...}
    },
    "Calhanoglu": {
        "records": [...],
        "attrs": {...}
    }
}
```

Key:

```text
player name
```

Value:

```text
player timeline database
```

---

# Structure of records

Each player owns a chronological timeline.

```json
{
    "records": [
        {...},
        {...}
    ]
}
```

Each record corresponds to one matchday.

---

## Core timeline fields

### giornata

Serie A matchday.

```json
"giornata": 8
```

Primary key component.

---

### status

Player usage status.

Examples:

```text
Titolare
Entrato
Infortunato
Squalificato
Inutilizzato
```

---

### status_code

Numeric status identifier.

Observed values:

```text
0 = Titolare
1 = Entrato
```

Other values may exist.

---

### played

Boolean.

```json
"played": true
```

Indicates a valid appearance.

---

### win

Match result from player's perspective.

Values:

```text
1  = win
0  = draw
-1 = loss
```

---

## Rating fields

### voto

Official Fantacalcio rating.

```json
"voto": 6.5
```

---

### fantavoto

Fantasy-adjusted rating.

```json
"fantavoto": 7.5
```

Includes goals, assists, cards and penalties.

Most predictive field in the dataset.

---

### voto_graph

Graph representation of voto.

Usually identical to:

```json
voto
```

---

### fantavoto_graph

Graph representation of fantavoto.

Usually identical to:

```json
fantavoto
```

---

## Participation metrics

### sub_in_minute

Minute of entry.

```json
64
```

Null if starter.

---

### sub_out_minute

Minute of substitution off.

```json
78
```

Null if never substituted.

---

## Market metrics

### quotazione_classic

Classic Fantacalcio quotation.

```json
33
```

Tracked at every matchday.

---

### quotazione_mantra

Mantra quotation.

```json
33
```

---

## Bonus / malus metrics

### bonus_graph

Positive fantasy contribution.

Common contributors:

```text
Goals
Assists
Penalty saves
```

Example:

```json
4.0
```

---

### malus_graph

Negative fantasy contribution.

Common contributors:

```text
Yellow cards
Red cards
Own goals
Missed penalties
```

Example:

```json
0.5
```

---

## Event counters

### assists

Total assists in the match.

```json
"assists": 1
```

---

### scoredGoals

Goals scored.

```json
"scoredGoals": 2
```

---

### yellowCards

Yellow cards.

```json
"yellowCards": 1
```

---

### redCards

Red cards.

```json
"redCards": 1
```

---

### ownGoals

Own goals.

```json
"ownGoals": 1
```

---

## Match information

### match_text

Human-readable result.

```json
"Int 5-0 Tor"
```

---

### team_home

Home team abbreviation.

```json
"Int"
```

---

### team_away

Away team abbreviation.

```json
"Tor"
```

---

### score_home

Goals scored by home team.

---

### score_away

Goals scored by away team.

---

### active_team

Player's team in that match.

Example:

```json
"Int"
```

---

### match_date

Official kickoff datetime.

```json
"2025-08-25T18:45:00Z"
```

---

### stadium

Match stadium.

```json
"Giuseppe Meazza"
```

---

### calendar_match_status

Inherited from official calendar.

```json
"FINISHED"
```

---

## Event structure

Field:

```json
"events": [...]
```

Structure:

```json
{
    "key": "scoredGoals",
    "title": "Gol segnati",
    "value": 1,
    "attrs": {...}
}
```

Typical keys:

```text
scoredGoals
assists
yellowCards
redCards
ownGoals
savedPenalties
missedPenalties
subIn
subOut
```

---

## event_counts

Flattened numerical event map.

Example:

```json
{
    "scoredGoals": 2,
    "assists": 1
}
```

Recommended over parsing events.

---

## record_type

Timeline row origin.

Allowed values:

```text
player_page
serie_a_calendar
```

Meaning:

| value | description |
|---------|---------|
| player_page | real Fantacalcio match record |
| serie_a_calendar | calendar placeholder/generated record |

---

# Structure of attrs

Each player contains metadata:

```json
{
    "records": [...],
    "attrs": {...}
}
```

---

## attrs overview

Contains season-level information and page metadata.

Typical sections:

```json
{
    "bridge": {...},
    "top_stats": {...},
    "summary_stats": {...},
    "dataset_stats": [...],
    "season_status_percent": [...],
    "graphs": {...},
    "preseason_price": {...}
}
```

---

## bridge

Canonical player identity.

```json
{
    "playerId": 2764,
    "playerPosition": "A",
    "playerName": "Martinez L.",
    "teamName": "Inter",
    "season": "2025-26"
}
```

Most reliable player identifier:

```json
playerId
```

---

## top_stats

Header statistics visible on Fantacalcio player page.

Example:

```json
{
    "Media Voto": 6.42,
    "Fantamedia": 8.25
}
```

---

## summary_stats

Season aggregates.

Examples:

```json
{
    "Gol": 15,
    "Assist": 7,
    "Partite a voto": 28,
    "Ammonizioni": 3
}
```

---

## dataset_stats

Flattened numerical representation of summary widgets.

```json
[
    {
        "name": "Gol",
        "value": 15
    }
]
```

Useful for ingestion and feature extraction.

---

## season_status_percent

Availability distribution.

Example:

```json
[
    {
        "name": "Titolare",
        "value": "27 - 71"
    }
]
```

Meaning:

```text
27 matches
71% of season
```

---

## graphs

Graph metadata extracted from Fantacalcio.

Sections:

```json
{
    "grades": {...},
    "bonuses": {...},
    "prices": {...}
}
```

Contains visual configuration plus underlying values.

---

## preseason_price

Player quotation before matchday 1.

```json
{
    "primary": 34,
    "secondary": 34
}
```

Useful for:

```python
quotation_growth =
current_price - preseason_price
```

---

# Recommended fields for analytics

For forecasting, ranking and dashboarding:

```text
giornata
played
status
win

voto
fantavoto

assists
scoredGoals
yellowCards
redCards
ownGoals

sub_in_minute
sub_out_minute

quotazione_classic
quotazione_mantra

team_home
team_away

score_home
score_away

match_date
```

The various:

```text
*_attrs
raw_row_html
graph metadata
```

are primarily debugging and migration artefacts and can usually be ignored by modelling pipelines.