from time import time_ns
import argparse
import json
import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Mapping
from urllib.parse import quote, urljoin

import re
import pandas as pd
try:
    from fantastat.timeline import TimelineIntegrityError
except Exception:
    class TimelineIntegrityError(RuntimeError):
        pass
import requests
import urllib3
urllib3.disable_warnings()
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _num(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None

    s = s.replace(".", "").replace(",", ".")

    try:
        x = float(s)
        return int(x) if x.is_integer() else x
    except ValueError:
        return s


def _attrs(tag):
    if not tag:
        return {}

    out = {}
    for k, v in tag.attrs.items():
        out[k] = " ".join(v) if isinstance(v, list) else v
    return out


def _meta_content(scope, selector, attr="content"):
    tag = scope.select_one(selector) if scope else None
    return tag.get(attr) if tag and tag.has_attr(attr) else None


def _graph_series(soup, section_id):
    """
    Extract graph data from:
    - player-grades-graph
      primary = Voto
      secondary = FantaVoto

    - player-bonuses-graph
      primary = Bonus
      secondary = Malus

    - player-price-graph
      primary = Classic
      secondary = Mantra
    """
    sec = soup.select_one(f"#{section_id}")
    if not sec:
        return {"meta": {}, "data": {}}

    frame = sec.select_one(".graph .frame")
    items = sec.select_one(".graph .items")

    legend = [
        _clean(li.get_text(" ", strip=True))
        for li in sec.select("figcaption .legend li")
    ]

    data = {}

    # x-axis has the clean data-primary-value / data-secondary-value
    for sp in sec.select(".x-axis span[data-x]"):
        x = _num(sp.get("data-x"))
        data[x] = {
            "primary": _num(sp.get("data-primary-value")),
            "secondary": _num(sp.get("data-secondary-value")),
            "tertiary": _num(sp.get("data-tertiary-value")),
            "x_axis_attrs": _attrs(sp),
        }

    # items contain the actual graph element attrs, style ratios, class none/invalid, etc.
    for item in sec.select(".items .item[data-x]"):
        x = _num(item.get("data-x"))
        rec = data.setdefault(x, {})

        pv = item.select_one(".primary-value")
        sv = item.select_one(".secondary-value")
        tv = item.select_one(".tertiary-value")

        rec.update(
            {
                "item_attrs": _attrs(item),
                "primary_item_value": _num(pv.get("data-value")) if pv else None,
                "secondary_item_value": _num(sv.get("data-value")) if sv else None,
                "tertiary_item_value": _num(tv.get("data-value")) if tv else None,
                "primary_item_attrs": _attrs(pv),
                "secondary_item_attrs": _attrs(sv),
                "tertiary_item_attrs": _attrs(tv),
            }
        )

    meta = {
        "section_id": section_id,
        "section_title": _clean(sec.select_one("h2.section-name").get_text(" ", strip=True))
        if sec.select_one("h2.section-name")
        else None,
        "legend": legend,
        "frame_attrs": _attrs(frame),
        "items_attrs": _attrs(items),
    }

    return {"meta": meta, "data": data}


def _extract_player_attrs(soup, source_url=None):
    main = soup.select_one("#player-main-info")
    meta_player = soup.select_one("#meta-player")

    attrs = {
        "source_url": source_url,
        "page_title": _clean(soup.title.get_text(strip=True)) if soup.title else None,
        "canonical_url": _meta_content(soup, "link[rel='canonical']", "href"),
        "og_url": _meta_content(soup, "meta[property='og:url']"),
        "og_image": _meta_content(soup, "meta[property='og:image']"),
        "meta_description": _meta_content(soup, "meta[name='description']"),
        "player_name": None,
        "team": None,
        "team_url": None,
        "birthdate_iso": None,
        "image": None,
        "description": None,
        "roles": [],
        "player_data": {},
        "top_stats": {},
        "summary_stats": {},
        "dataset_stats": [],
        "season_status_percent": [],
        "download_player_detail_href": None,
        "bridge": {},
    }

    if main:
        name = main.select_one("h1.player-name")
        team = main.select_one("a.team-name")

        attrs["player_name"] = _clean(name.get_text(" ", strip=True)) if name else None
        attrs["team"] = _clean(team.get_text(" ", strip=True)) if team else None
        attrs["team_url"] = team.get("href") if team else None
        attrs["description"] = (
            _clean(main.select_one(".description").get_text(" ", strip=True))
            if main.select_one(".description")
            else None
        )

        attrs["roles"] = [
            {
                "data_value": sp.get("data-value"),
                "title": sp.get("title"),
                "attrs": _attrs(sp),
            }
            for sp in main.select(".role-pill .role")
        ]

        for div in main.select("dl.player-data > div"):
            dt = div.select_one("dt")
            dd = div.select_one("dd")
            if dt and dd:
                key = _clean(dt.get_text(" ", strip=True))
                attrs["player_data"][key] = {
                    "text": _clean(dd.get_text(" ", strip=True)),
                    "attrs": _attrs(dd),
                }

        for group in main.select(".player-stats .group"):
            label = group.select_one("label.small-label")
            gname = _clean(label.get_text(" ", strip=True)) if label else None

            values = []
            for li in group.select("li"):
                badge = li.select_one(".badge")
                small = li.select_one(".small-label")

                values.append(
                    {
                        "title": li.get("title"),
                        "value": _num(_clean(badge.get_text(" ", strip=True))) if badge else None,
                        "label": _clean(small.get_text(" ", strip=True)) if small else None,
                        "li_attrs": _attrs(li),
                    }
                )

            if gname:
                attrs["top_stats"][gname] = values

    if meta_player:
        attrs["birthdate_iso"] = _meta_content(meta_player, "meta[itemprop='birthdate']")
        attrs["image"] = _meta_content(meta_player, "meta[itemprop='image']")

    # Dataset stats: MV, FM, quotazioni, plus season summary
    for sec_id in ["meta-dataset-stats", "player-summary-stats"]:
        sec = soup.select_one(f"#{sec_id}")
        if not sec:
            continue

        for vm in sec.select('[itemprop="variableMeasured"]'):
            name_tag = vm.select_one('[itemprop~="name"]')
            val_tag = vm.select_one('[itemprop="value"]')

            if name_tag and name_tag.name == "meta":
                name = name_tag.get("content")
            elif name_tag:
                name = _clean(name_tag.get_text(" ", strip=True))
            else:
                name = None

            if val_tag and val_tag.name == "meta":
                value = val_tag.get("content")
            elif val_tag:
                value = _clean(val_tag.get_text(" ", strip=True))
            else:
                value = None

            rec = {
                "name": name,
                "value": _num(value),
                "attrs": _attrs(vm),
            }

            if sec_id == "player-summary-stats":
                attrs["summary_stats"][name] = rec
            else:
                attrs["dataset_stats"].append(rec)

    # Donut summary: Titolare, Entrato, Squalificato, Infortunato, Inutilizzato
    sec = soup.select_one("#meta-dataset-status-percent")
    if sec:
        for li in sec.select('li[itemprop="variableMeasured"]'):
            name = (
                _clean(li.select_one('[itemprop~="name"]').get_text(" ", strip=True))
                if li.select_one('[itemprop~="name"]')
                else None
            )
            value = (
                _clean(li.select_one('[itemprop="value"]').get_text(" ", strip=True))
                if li.select_one('[itemprop="value"]')
                else None
            )

            attrs["season_status_percent"].append(
                {
                    "name": name,
                    "value": value,
                    "attrs": _attrs(li),
                }
            )

    dl = soup.select_one("#download-control[href]")
    if dl:
        attrs["download_player_detail_href"] = dl.get("href")

    # Bridge JS block: playerId, playerPosition, playerName, teamName, season, etc.
    script = soup.find("script", string=re.compile(r"var\s+Bridge\s*="))
    if script and script.string:
        txt = script.string

        pairs = re.findall(
            r"(\w+)\s*:\s*(\"[^\"]*\"|'[^']*'|true|false|null|-?\d+(?:\.\d+)?)",
            txt,
        )

        for k, v in pairs:
            v = v.strip()

            if v.startswith(("'", '"')):
                v = v[1:-1]
            elif v == "true":
                v = True
            elif v == "false":
                v = False
            elif v == "null":
                v = None
            else:
                v = _num(v)

            attrs["bridge"][k] = v

    return attrs


PLAYER_MATCH_COLUMNS = ['giornata', 'status', 'status_code', 'match_url', 'match_text', 'team_home', 'team_away', 'score_home', 'score_away', 'active_team', 'win', 'voto', 'fantavoto', 'voto_graph', 'fantavoto_graph', 'sub_in_minute', 'sub_out_minute', 'bonus_graph', 'malus_graph', 'quotazione_classic', 'quotazione_mantra', 'events', 'event_counts', 'assists', 'scoredGoals', 'yellowCards', 'redCards', 'ownGoals', 'row_attrs', 'matchweek_attrs', 'match_attrs', 'grade_attrs', 'fanta_grade_attrs', 'sub_in_attrs', 'sub_out_attrs', 'status_stripe_attrs', 'grade_graph_attrs', 'bonus_malus_graph_attrs', 'price_graph_attrs', 'raw_row_html', 'record_type', 'played', 'is_placeholder', 'match_date', 'match_time', 'stadium', 'calendar_match_status']


def scrape_fantacalcio_player(
    path_or_url,
    *,
    proxies=None,
    headers=None,
    timeout=30,
    verify=True,
):
    """
    Scrape a Fantacalcio player detail page.

    Input:
      - local HTML path
      - raw HTML string
      - URL

    Output:
      - pandas DataFrame
      - one row per giornata
      - player generalità/descrizione/summary attrs in df.attrs
      - HTML attributes preserved in dedicated *_attrs columns
    """

    source_url = None

    if isinstance(path_or_url, str) and path_or_url.lstrip().startswith("<"):
        html = path_or_url

    elif re.match(r"^https?://", str(path_or_url)):
        source_url = str(path_or_url)

        r = requests.get(
            source_url,
            proxies=proxies,
            headers=headers or {"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
            verify=verify,
        )
        r.raise_for_status()
        html = r.text

    else:
        html = Path(path_or_url).read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")

    player_attrs = _extract_player_attrs(soup, source_url=source_url)

    grade_graph = _graph_series(soup, "player-grades-graph")
    bonus_graph = _graph_series(soup, "player-bonuses-graph")
    price_graph = _graph_series(soup, "player-price-graph")

    # Status in text form: Titolare, Entrato, Inutilizzato, etc.
    status_by_gw = {}
    sec = soup.select_one("#meta-dataset-status")

    if sec:
        for vm in sec.select('[itemprop="variableMeasured"]'):
            name = _meta_content(vm, 'meta[itemprop~="name"]')
            value = _meta_content(vm, 'meta[itemprop="value"]')

            m = re.search(r"(\d+)", name or "")
            if m:
                status_by_gw[int(m.group(1))] = value

    # Status stripe attributes from visual component
    stripe_by_gw = {}
    for sp in soup.select("#player-season-table .dot-stripe .value[data-count]"):
        gw = _num(sp.get("data-count"))
        li = sp.find_parent("li")

        stripe_by_gw[gw] = {
            "attrs": _attrs(sp),
            "parent_attrs": _attrs(li),
        }

    records = []

    for tr in soup.select("#player-season-table table.player-summary-table tbody tr"):
        if "divider" in (tr.get("class") or []):
            continue

        mw = tr.select_one(".matchweek")
        if not mw:
            continue

        giornata = int(_clean(mw.get_text(" ", strip=True)))

        match = tr.select_one("a.match")
        active = match.select_one(".active") if match else None

        home = (
            _clean(match.select_one(".team-home").get_text(" ", strip=True))
            if match and match.select_one(".team-home")
            else None
        )

        away = (
            _clean(match.select_one(".team-away").get_text(" ", strip=True))
            if match and match.select_one(".team-away")
            else None
        )

        score = (
            _clean(match.select_one(".match-score").get_text(" ", strip=True))
            if match and match.select_one(".match-score")
            else None
        )

        grade = tr.select_one(".grade")
        fgrade = tr.select_one(".fanta-grade")
        sub_in = tr.select_one(".sub-in")
        sub_out = tr.select_one(".sub-out")

        events = []
        event_counts = Counter()

        for fig in tr.select(".events figure.bonus-icon"):
            key = fig.get("data-key")
            value = _num(fig.get("data-value"))
            title = fig.get("title")

            events.append(
                {
                    "key": key,
                    "title": title,
                    "value": value,
                    "attrs": _attrs(fig),
                }
            )

            if key:
                event_counts[key] += value if isinstance(value, (int, float)) else 1

        score_home, score_away = None, None
        if score and "-" in score:
            try:
                left, right = score.split("-", 1)
                score_home = int(left.strip())
                score_away = int(right.strip())
            except ValueError:
                score_home, score_away = None, None

        active_team = _clean(active.get_text(" ", strip=True)) if active else None
        win_flag = None
        if score_home is not None and score_away is not None:
            if score_home == score_away:
                win_flag = 0
            elif active_team == home and score_home > score_away:
                win_flag = 1
            elif active_team == away and score_away > score_home:
                win_flag = 1
            else:
                win_flag = -1


        g_graph = grade_graph["data"].get(giornata, {})
        b_graph = bonus_graph["data"].get(giornata, {})
        p_graph = price_graph["data"].get(giornata, {})

        records.append(
            {
                "giornata": giornata,

                # Riepilogo stagione
                "status": status_by_gw.get(giornata),
                "status_code": _num(
                    (stripe_by_gw.get(giornata, {}).get("attrs") or {}).get("data-value")
                ),

                # Match
                "match_url": match.get("href") if match else None,
                "match_text": _clean(match.get_text(" ", strip=True)) if match else None,
                "team_home": home,
                "team_away": away,
                "score_home": score_home,
                "score_away": score_away,
                "active_team": active_team,
                "win": win_flag,

                # Voto e Fantavoto from table
                "voto": _num(grade.get("data-value")) if grade else None,
                "fantavoto": _num(fgrade.get("data-value")) if fgrade else None,

                # Voto e Fantavoto from graph attrs
                "voto_graph": g_graph.get("primary"),
                "fantavoto_graph": g_graph.get("secondary"),

                # Sub
                "sub_in_minute": _num(sub_in.get("data-minute")) if sub_in else None,
                "sub_out_minute": _num(sub_out.get("data-minute")) if sub_out else None,

                # Bonus e Malus graph
                "bonus_graph": b_graph.get("primary"),
                "malus_graph": b_graph.get("secondary"),

                # Prices graph
                "quotazione_classic": p_graph.get("primary"),
                "quotazione_mantra": p_graph.get("secondary"),

                # Events
                "events": events,
                "event_counts": dict(event_counts),
                "assists": event_counts.get("assists", 0),
                "scoredGoals": event_counts.get("scoredGoals", 0),
                "yellowCards": event_counts.get("yellowCards", 0),
                "redCards": event_counts.get("redCards", 0),
                "ownGoals": event_counts.get("ownGoals", 0),

                # Raw HTML attributes
                "row_attrs": _attrs(tr),
                "matchweek_attrs": _attrs(mw),
                "match_attrs": _attrs(match),
                "grade_attrs": _attrs(grade),
                "fanta_grade_attrs": _attrs(fgrade),
                "sub_in_attrs": _attrs(sub_in),
                "sub_out_attrs": _attrs(sub_out),
                "status_stripe_attrs": stripe_by_gw.get(giornata),

                # Full graph attrs for this giornata
                "grade_graph_attrs": g_graph,
                "bonus_malus_graph_attrs": b_graph,
                "price_graph_attrs": p_graph,

                # Optional debugging
                "raw_row_html": str(tr),
                "record_type": "player_page",
                "played": True,
                "is_placeholder": False,
                "match_date": None,
                "match_time": None,
                "stadium": None,
                "calendar_match_status": None,
            }
        )

    if records:
        df = pd.DataFrame(records).reindex(columns=PLAYER_MATCH_COLUMNS)
        df = df.sort_values("giornata").reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=PLAYER_MATCH_COLUMNS)

    # Generalità, descrizione, summary, ruolo, Bridge, ecc.
    df.attrs.update(player_attrs)

    # The complete quotation-graph x-axis defines expected matchweeks,
    # including graph entries whose quotation values are null.
    price_graph_matchweeks = sorted(int(g) for g in price_graph.get("data", {}) if isinstance(g, int) and g > 0)
    df.attrs["graphs"] = {
        "grades": grade_graph["meta"],
        "bonuses": bonus_graph["meta"],
        "prices": price_graph["meta"],
    }
    df.attrs["price_graph_matchweeks"] = price_graph_matchweeks
    df.attrs["price_graph_max_matchweek"] = max(price_graph_matchweeks, default=None)
    df.attrs["scraper_schema_version"] = SCRAPER_SCHEMA_VERSION

    # Quotazione pre-campionato, x=0
    if 0 in price_graph["data"]:
        df.attrs["preseason_price"] = price_graph["data"][0]

    return df



DEFAULT_BASE_URL = "https://www.fantacalcio.it"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_TIMEOUT = 30
SCRAPER_SCHEMA_VERSION = 5

SERIE_A_API_BASE_URL = "https://api-sdp.legaseriea.it/v1/serie-a/football"
SERIE_A_COMPETITION_ID = "serie-a::Football_Competition::ec93b94f74294dc98ab5bcfd67fc0d88"
VALID_RECORD_TYPES = {"serie_a_calendar", "player_page"}

TEAM_ALIASES = {
    "ata": "atalanta", "atlanta": "atalanta",
    "bol": "bologna", "cag": "cagliari", "com": "como",
    "cre": "cremonese", "emp": "empoli", "fio": "fiorentina",
    "gen": "genoa", "ver": "hellas verona", "hel": "hellas verona", "hve": "hellas verona",
    "int": "inter", "internazionale": "inter", "juv": "juventus",
    "laz": "lazio", "lec": "lecce", "mil": "milan", "ac milan": "milan",
    "mon": "monza", "nap": "napoli", "par": "parma", "pis": "pisa",
    "rom": "roma", "sas": "sassuolo", "tor": "torino", "udi": "udinese", "ven": "venezia",
}


def time_s():
    return time_ns() / 1.0e9


def season_from_reference_year(reference_year: int) -> str:
    """Convert 2026 -> '2025-26', 2025 -> '2024-25', etc."""
    year = int(reference_year)
    return f"{year - 1}-{str(year)[-2:]}"


def serie_a_api_season_name(reference_year: int) -> str:
    """Convert 2025 -> '2024/2025' for the Lega Serie A SDP API."""
    year = int(reference_year)
    return f"{year - 1}/{year}"


def quotazioni_url(reference_year: int, base_url: str = DEFAULT_BASE_URL) -> str:
    season = season_from_reference_year(reference_year)
    return urljoin(base_url.rstrip("/") + "/", f"quotazioni-fantacalcio/{season}")


def _normalise_team_key(value: Any) -> str:
    text = _clean(str(value or "")).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return TEAM_ALIASES.get(text, text)


def _first_present(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _as_int_or_none(value: Any) -> int | None:
    value = _num(value)
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def make_calendar_record(fixture: Mapping[str, Any], team: str | None = None) -> dict[str, Any]:
    row = {column: None for column in PLAYER_MATCH_COLUMNS}
    for column in (
        "giornata", "match_url", "match_text", "team_home", "team_away",
        "score_home", "score_away", "match_date", "match_time", "stadium",
        "calendar_match_status",
    ):
        row[column] = fixture.get(column)

    active_team = team or fixture.get("active_team")
    row["active_team"] = active_team
    row["status"] = fixture.get("status") or "scheduled"
    row["status_code"] = fixture.get("status_code")

    if active_team and row["score_home"] is not None and row["score_away"] is not None:
        key = _normalise_team_key(active_team)
        home_key = _normalise_team_key(row["team_home"])
        away_key = _normalise_team_key(row["team_away"])
        diff = int(row["score_home"]) - int(row["score_away"])
        if key == home_key:
            row["win"] = 1 if diff > 0 else -1 if diff < 0 else 0
        elif key == away_key:
            row["win"] = 1 if diff < 0 else -1 if diff > 0 else 0

    row.update({
        "events": [], "event_counts": {},
        "assists": 0, "scoredGoals": 0, "yellowCards": 0, "redCards": 0, "ownGoals": 0,
        "row_attrs": {}, "matchweek_attrs": {}, "match_attrs": {}, "grade_attrs": {},
        "fanta_grade_attrs": {}, "sub_in_attrs": {}, "sub_out_attrs": {},
        "status_stripe_attrs": {}, "grade_graph_attrs": {},
        "bonus_malus_graph_attrs": {}, "price_graph_attrs": {},
        "record_type": "serie_a_calendar", "played": False, "is_placeholder": True,
    })
    return row


def resolve_team_from_calendar(calendar_df: pd.DataFrame, *candidates: Any) -> str | None:
    known: dict[str, str] = {}
    for column in ("team_home", "team_away"):
        if column not in calendar_df.columns:
            continue
        for team in calendar_df[column].dropna().astype(str):
            known[_normalise_team_key(team)] = team

    for candidate in candidates:
        if candidate is None or pd.isna(candidate):
            continue
        key = _normalise_team_key(candidate)
        if key in known:
            return known[key]

    for candidate in candidates:
        if candidate is None or pd.isna(candidate):
            continue
        key = _normalise_team_key(candidate)
        matches = [full for normalised, full in known.items() if normalised.startswith(key) or key.startswith(normalised)]
        if len(set(matches)) == 1:
            return matches[0]
    return None


def resolve_calendar_team(
    player_df: pd.DataFrame,
    quotation_team: Any,
    calendar_df: pd.DataFrame,
    team_slug: Any = None,
) -> str | None:
    bridge = player_df.attrs.get("bridge", {}) if isinstance(player_df.attrs.get("bridge"), Mapping) else {}
    candidates = [player_df.attrs.get("team"), bridge.get("teamName"), team_slug, quotation_team]
    team_url = player_df.attrs.get("team_url")
    if team_url:
        slug = str(team_url).rstrip("/").rsplit("/", 1)[-1]
        candidates.append(slug.replace("-", " "))
    return resolve_team_from_calendar(calendar_df, *candidates)


def calendar_records_for_team(calendar_df: pd.DataFrame, team: str | None) -> pd.DataFrame:
    if not team or calendar_df.empty:
        return pd.DataFrame(columns=PLAYER_MATCH_COLUMNS)
    key = _normalise_team_key(team)
    home = calendar_df["team_home"].fillna("").astype(str).map(_normalise_team_key)
    away = calendar_df["team_away"].fillna("").astype(str).map(_normalise_team_key)
    schedule = calendar_df.loc[(home == key) | (away == key)].copy()
    rows = [make_calendar_record(row, team) for row in schedule.to_dict("records")]
    result = pd.DataFrame(rows, columns=PLAYER_MATCH_COLUMNS)
    result = result.sort_values("giornata").reset_index(drop=True) if not result.empty else result
    result.attrs["calendar_team_resolved"] = team
    result.attrs["calendar_season"] = calendar_df.attrs.get("season")
    result.attrs["calendar_source"] = "legaseriea_sdp_api"
    result.attrs["scraper_schema_version"] = SCRAPER_SCHEMA_VERSION
    return result


def merge_player_page_into_calendar(base_df: pd.DataFrame, player_df: pd.DataFrame) -> pd.DataFrame:
    base_attrs = dict(base_df.attrs)
    player_attrs = dict(player_df.attrs)
    base = base_df.reindex(columns=PLAYER_MATCH_COLUMNS).copy()
    page = player_df.reindex(columns=PLAYER_MATCH_COLUMNS).copy()

    if base.empty:
        result = page
        result.attrs.update(player_attrs)
        result.attrs.setdefault("scraper_schema_version", SCRAPER_SCHEMA_VERSION)
        return result.sort_values("giornata").reset_index(drop=True)

    indexed: dict[int, dict[str, Any]] = {}
    for row in base.to_dict("records"):
        g = _as_int_or_none(row.get("giornata"))
        if g is not None:
            indexed[g] = row

    for row in page.to_dict("records"):
        g = _as_int_or_none(row.get("giornata"))
        if g is None:
            continue
        api_row = indexed.get(g, {})
        merged = dict(api_row) if api_row else {column: None for column in PLAYER_MATCH_COLUMNS}
        for column in PLAYER_MATCH_COLUMNS:
            value = row.get(column)
            if value is not None and value is not pd.NA:
                merged[column] = value
        for column in ("team_home", "team_away", "score_home", "score_away", "match_date", "match_time", "stadium", "calendar_match_status"):
            if merged.get(column) is None and api_row.get(column) is not None:
                merged[column] = api_row[column]
        merged["record_type"] = "player_page"
        merged["played"] = True
        merged["is_placeholder"] = False
        indexed[g] = merged

    result = pd.DataFrame([indexed[g] for g in sorted(indexed)], columns=PLAYER_MATCH_COLUMNS)
    result.attrs.update(base_attrs)
    result.attrs.update(player_attrs)
    result.attrs["scraper_schema_version"] = SCRAPER_SCHEMA_VERSION
    return result


def validate_player_timeline(df: pd.DataFrame, *, player: str, requested_year: int | None = None) -> None:
    if df.empty:
        raise TimelineIntegrityError(f"Timeline integrity failure for {player}: empty timeline")
    giornate = pd.to_numeric(df["giornata"], errors="coerce")
    invalid = df.loc[giornate.isna()].index.tolist()
    values = giornate.dropna().astype(int).tolist()
    duplicates = sorted([g for g, n in Counter(values).items() if n > 1])
    missing = sorted(set(range(1, max(values) + 1)) - set(values)) if values else []
    invalid_record_type_rows = [
        int(i) for i, value in df.get("record_type", pd.Series([], dtype=object)).items()
        if value not in VALID_RECORD_TYPES
    ]
    if missing or duplicates or invalid or invalid_record_type_rows:
        raise TimelineIntegrityError(
            f"Timeline integrity failure for {player}: "
            f"missing={missing}, duplicates={duplicates}, invalid_giornata_rows={invalid}, "
            f"invalid_record_type_rows={invalid_record_type_rows}"
        )

def _json_clean(obj: Any) -> Any:
    """Make nested pandas/numpy objects JSON-safe."""
    if isinstance(obj, pd.DataFrame):
        return dataframe_to_payload(obj)
    if isinstance(obj, Mapping):
        return {str(k): _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_clean(v) for v in obj]
    if obj is pd.NA:
        return None
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return None if pd.isna(obj) else float(obj)
        if isinstance(obj, np.ndarray):
            return [_json_clean(v) for v in obj.tolist()]
    except Exception:
        pass
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return obj


def dataframe_to_payload(df: pd.DataFrame) -> dict[str, Any]:
    """Serialize a player stats DataFrame preserving df.attrs."""
    safe_df = df.astype(object).where(pd.notna(df), None)
    return {
        "records": _json_clean(safe_df.to_dict(orient="records")),
        "attrs": _json_clean(dict(df.attrs)),
    }


def payload_to_dataframe(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Deserialize a player stats DataFrame from cache payload."""
    df = pd.DataFrame(payload.get("records", []))
    attrs = payload.get("attrs", {})
    if isinstance(attrs, Mapping):
        df.attrs.update(dict(attrs))
    return df


def _extract_matchday(match: Mapping[str, Any], match_set: Mapping[str, Any]) -> int | None:
    """
    Extract Serie A matchday.

    Important:
    Do not blindly parse any trailing number from providerId.
    providerId can be an internal Opta id, not the matchday.
    """

    candidates = [
        match.get("matchDay"),
        match.get("matchday"),
        match.get("matchWeek"),
        match.get("matchweek"),
        match.get("round"),
        match_set.get("matchDay"),
        match_set.get("matchday"),
        match_set.get("matchWeek"),
        match_set.get("matchweek"),
        match_set.get("round"),
        match_set.get("name"),
        match_set.get("displayName"),
    ]

    for value in candidates:
        if value is None:
            continue

        if isinstance(value, int):
            if 1 <= value <= 38:
                return value

        text = str(value)

        # Accept explicit forms only.
        patterns = [
            r"MatchDay:(\d+)",
            r"Matchday:(\d+)",
            r"Match Day\s*(\d+)",
            r"Matchday\s*(\d+)",
            r"Giornata\s*(\d+)",
            r"Round\s*(\d+)",
            r"^(\d+)$",
        ]

        for pattern in patterns:
            found = re.search(pattern, text, flags=re.IGNORECASE)
            if found:
                day = int(found.group(1))
                if 1 <= day <= 38:
                    return day

    # providerId is accepted only if it explicitly says MatchDay.
    provider_id = match_set.get("providerId")
    if provider_id:
        text = str(provider_id)
        found = re.search(r"MatchDay:(\d+)", text, flags=re.IGNORECASE)
        if found:
            day = int(found.group(1))
            if 1 <= day <= 38:
                return day

    return None


@dataclass(slots=True)
class ScraperConfig:
    reference_year: int
    base_url: str = DEFAULT_BASE_URL
    cache_dir: Path | str = Path("cache")
    max_cache_age: timedelta = timedelta(days=1)
    timeout: int = DEFAULT_TIMEOUT
    headers: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    proxies: dict[str, str] | None = None
    verify: bool = True
    max_workers: int = 10

    @property
    def season(self) -> str:
        return season_from_reference_year(self.reference_year)

    @property
    def quotazioni_url(self) -> str:
        return quotazioni_url(self.reference_year, self.base_url)

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir)

    @property
    def quotazioni_cache_file(self) -> Path:
        return self.cache_path / f"quotazioni{self.reference_year}.csv"

    @property
    def stats_cache_file(self) -> Path:
        return self.cache_path / f"stats{self.reference_year}.json"

    @property
    def calendar_cache_file(self) -> Path:
        return self.cache_path / f"calendar{self.reference_year}.json"


class FileCache:
    """Small file cache with age-based invalidation."""

    def __init__(self, cache_dir: Path | str, max_age: timedelta = timedelta(days=1)):
        self.cache_dir = Path(cache_dir)
        self.max_age = max_age
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_seconds = time_s() - path.stat().st_mtime
        return age_seconds < self.max_age.total_seconds()

    def read_csv(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path)

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, obj: Any, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_json_clean(obj), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )



class FantacalcioHTTPClient:
    """HTTP wrapper: keeps proxies/headers/timeout in one reusable place."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        verify: bool = True,
        session: requests.Session | None = None,
    ):
        self.headers = headers or dict(DEFAULT_HEADERS)
        self.proxies = proxies
        self.timeout = timeout
        self.verify = verify
        self.session = session or requests.Session()

    def get_text(self, url: str) -> str:
        response = self.session.get(url, headers=self.headers, proxies=self.proxies, timeout=self.timeout, verify=self.verify)
        response.raise_for_status()
        return response.text

    def get_json(self, url: str) -> Any:
        response = self.session.get(url, headers=self.headers, proxies=self.proxies, timeout=self.timeout, verify=self.verify)
        response.raise_for_status()
        return response.json()


class PlayerDetailScraper:
    """Reusable scraper for a single player detail page."""

    def __init__(self, client: FantacalcioHTTPClient):
        self.client = client

    def scrape(self, path_or_url: str) -> pd.DataFrame:
        if re.match(r"^https?://", str(path_or_url)):
            html = self.client.get_text(str(path_or_url))
            return scrape_fantacalcio_player(html)
        return scrape_fantacalcio_player(path_or_url)


class QuotazioniScraper:
    """Scraper for the Fantacalcio quotazioni table."""

    def __init__(self, client: FantacalcioHTTPClient, base_url: str = DEFAULT_BASE_URL):
        self.client = client
        self.base_url = base_url

    def scrape(self, reference_year: int) -> pd.DataFrame:
        url = quotazioni_url(reference_year, self.base_url)
        html = self.client.get_text(url)
        return self.parse(html)

    def parse(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "html.parser")
        players: list[dict[str, Any]] = []
        for tr in soup.select("#prices table tbody tr"):
            a = tr.select_one("a[href]")
            if not a:
                continue
            role = tr.select_one("th span.role")
            team = tr.select_one("td.player-team")
            qi = tr.select_one("td.player-classic-initial-price")
            qa = tr.select_one("td.player-classic-current-price")
            fvm = tr.select_one("td.player-classic-fvm")
            href = a.get("href")
            row = {
                "url": urljoin(self.base_url, href),
                "team_slug": self._team_slug_from_url(href),
                "nome": _clean(a.get_text(" ", strip=True)),
                "ruolo": role.get("data-value", "").upper() if role else None,
                "squadra": _clean(team.get_text(" ", strip=True)) if team else None,
                "QI": _num(qi.get_text(" ", strip=True)) if qi else None,
                "QA": _num(qa.get_text(" ", strip=True)) if qa else None,
                "FVM": _num(fvm.get_text(" ", strip=True)) if fvm else None,
            }
            players.append(row)
        return pd.DataFrame(players)

    @staticmethod
    def _team_slug_from_url(href: str | None) -> str | None:
        if not href:
            return None
        found = re.search(r"/squadre/([^/]+)/", href)
        return found.group(1).replace("-", " ") if found else None


class SerieAApiScraper:
    """Lega Serie A SDP API client for seasons and matches."""

    def __init__(self, client: FantacalcioHTTPClient, api_base_url: str = SERIE_A_API_BASE_URL):
        self.client = client
        self.api_base_url = api_base_url.rstrip("/")

    def _url(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        return f"{self.api_base_url}{path}{separator}locale=en-GB"

    def get_json(self, path: str) -> Any:
        return self.client.get_json(self._url(path))

    def season_id_for_reference_year(self, reference_year: int) -> tuple[str, str]:
        target = serie_a_api_season_name(reference_year)
        comp = quote(SERIE_A_COMPETITION_ID, safe="")
        payload = self.get_json(f"/competitions/{comp}/seasons")
        seasons = payload.get("seasons", payload if isinstance(payload, list) else [])
        for season in seasons:
            if isinstance(season, Mapping) and season.get("seasonName") == target:
                return season["seasonId"], target.replace("/", "-")
        available = [s.get("seasonName") for s in seasons if isinstance(s, Mapping)]
        raise ValueError(f"Serie A API season {target!r} not found. Available examples: {available[:5]}")

    def scrape_calendar(self, reference_year: int) -> pd.DataFrame:
        season_id, season_name = self.season_id_for_reference_year(reference_year)
        payload = self.get_json(f"/seasons/{quote(season_id, safe='')}/matches")
        matches = payload.get("matches", payload if isinstance(payload, list) else [])
        rows = [self._parse_match(match) for match in matches if isinstance(match, Mapping)]
        calendar = pd.DataFrame(rows)
        if not calendar.empty:
            calendar = calendar.drop_duplicates(["giornata", "team_home", "team_away"]).sort_values(
                ["giornata", "match_date"], na_position="last"
            ).reset_index(drop=True)
        calendar.attrs["season"] = season_name
        calendar.attrs["season_id"] = season_id
        calendar.attrs["source"] = "legaseriea_sdp_api"
        return calendar

    def _parse_match(self, match: Mapping[str, Any]) -> dict[str, Any]:
        home = _first_present(match, "home", "homeTeam", "homeClub") or {}
        away = _first_present(match, "away", "awayTeam", "awayClub") or {}
        match_set = _first_present(match, "matchSet", "matchday", "round") or {}
        status = _first_present(match, "status", "matchStatus", "statusDescription")
        home_score = _first_present(match, "providerHomeScore", "homeScore", "scoreHome")
        away_score = _first_present(match, "providerAwayScore", "awayScore", "scoreAway")
        date_value = _first_present(match, "matchDateUtc", "kickOffUtc", "dateUtc", "matchDate")
        giornata = _extract_matchday(match, match_set)
        return {
            "giornata": _as_int_or_none(giornata),
            "match_url": None,
            "match_text": f"{self._team_name(home)} - {self._team_name(away)}",
            "team_home": self._team_name(home),
            "team_away": self._team_name(away),
            "score_home": _as_int_or_none(home_score),
            "score_away": _as_int_or_none(away_score),
            "match_date": date_value,
            "match_time": None,
            "stadium": _first_present(match, "stadiumName", "venueName"),
            "calendar_match_status": status,
            "status": status,
            "status_code": status,
            "raw_serie_a_match": match,
        }

    @staticmethod
    def _team_name(team: Mapping[str, Any]) -> str | None:
        return _first_present(team, "name", "officialName", "teamName", "shortName", "displayName")


class FantacalcioRunner:
    """
    High-level orchestration.

    Returns:
        (quotazioni_df, stats)
        where stats is dict[player_name, player_stats_dataframe].
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.cache = FileCache(config.cache_path, config.max_cache_age)
        self.client = FantacalcioHTTPClient(
            headers=config.headers,
            proxies=config.proxies,
            timeout=config.timeout,
            verify=config.verify,
        )
        self.quotazioni_scraper = QuotazioniScraper(self.client, config.base_url)
        self.player_scraper = PlayerDetailScraper(self.client)
        self.serie_a_scraper = SerieAApiScraper(self.client)

    def load_or_scrape_quotazioni(self, force: bool = False) -> pd.DataFrame:
        path = self.config.quotazioni_cache_file
        if not force and self.cache.is_fresh(path):
            print(f"Reading cached quotazioni: {path}")
            return self.cache.read_csv(path)
        print(f"Scraping quotazioni {self.config.season}: {self.config.quotazioni_url}")
        start = time_s()
        df = self.quotazioni_scraper.scrape(self.config.reference_year)
        self.cache.write_csv(df, path)
        print(f"Saved {len(df)} rows to {path} in {time_s() - start:.02f}s")
        return df

    def load_or_scrape_calendar(self, force: bool = False) -> pd.DataFrame:
        path = self.config.calendar_cache_file
        if not force and self.cache.is_fresh(path):
            return payload_to_dataframe(self.cache.read_json(path))
        print(f"Scraping Serie A API calendar for {serie_a_api_season_name(self.config.reference_year)}")
        calendar = self.serie_a_scraper.scrape_calendar(self.config.reference_year)
        self.cache.write_json(dataframe_to_payload(calendar), path)
        print(f"Saved {len(calendar)} fixtures to {path}")
        return calendar

    def load_or_scrape_stats(self, quotazioni: pd.DataFrame, force: bool = False) -> dict[str, pd.DataFrame]:
        path = self.config.stats_cache_file
        if not force and self.cache.is_fresh(path):
            payload = self.cache.read_json(path)
            cached_stats = {name: payload_to_dataframe(data) for name, data in payload.items()}
            if cached_stats and all(df.attrs.get("scraper_schema_version") == SCRAPER_SCHEMA_VERSION for df in cached_stats.values()):
                try:
                    for name, df in cached_stats.items():
                        validate_player_timeline(df, player=name, requested_year=self.config.reference_year)
                except TimelineIntegrityError as exc:
                    print(f"Ignoring invalid stats cache {path}: {exc}")
                else:
                    print(f"Reading cached stats: {path}")
                    return cached_stats
            print(f"Ignoring cached stats with obsolete schema: {path}")

        calendar = self.load_or_scrape_calendar(force=force)
        print(f"Building Serie A API baseline records for {len(quotazioni)} players")
        baseline = self.build_calendar_baseline(quotazioni, calendar)
        print(f"Scraping player stats with {self.config.max_workers} workers")
        start = time_s()
        stats = self.scrape_stats_parallel(quotazioni, calendar, baseline)
        for name, df in stats.items():
            try:
                validate_player_timeline(df, player=name, requested_year=self.config.reference_year)
            except TimelineIntegrityError as exc:
                raise TimelineIntegrityError(
                    f"{exc}; calendar_team={df.attrs.get('calendar_team_resolved')!r}, "
                    f"quotation_team={df.attrs.get('quotation_team')!r}, player_team={df.attrs.get('team')!r}"
                ) from exc
        payload = {name: dataframe_to_payload(df) for name, df in stats.items()}
        self.cache.write_json(payload, path)
        print(f"Saved stats for {len(stats)} players to {path} in {time_s() - start:.02f}s")
        return stats

    def build_calendar_baseline(self, quotazioni: pd.DataFrame, calendar: pd.DataFrame) -> dict[str, pd.DataFrame]:
        required = {"nome", "squadra"}
        missing = required - set(quotazioni.columns)
        if missing:
            raise ValueError(f"quotazioni is missing columns: {sorted(missing)}")
        baseline: dict[str, pd.DataFrame] = {}
        for row in quotazioni.to_dict("records"):
            name = str(row["nome"])
            team = resolve_team_from_calendar(calendar, row.get("team_slug"), row.get("squadra"))
            df = calendar_records_for_team(calendar, team)
            df.attrs["calendar_team_resolved"] = team
            df.attrs["quotation_team"] = row.get("squadra")
            df.attrs["quotation_team_slug"] = row.get("team_slug")
            baseline[name] = df
        return baseline

    def scrape_stats_parallel(
        self,
        quotazioni: pd.DataFrame,
        calendar: pd.DataFrame,
        baseline: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        required = {"nome", "url", "squadra"}
        missing = required - set(quotazioni.columns)
        if missing:
            raise ValueError(f"quotazioni is missing columns: {sorted(missing)}")
        selected = [column for column in ["nome", "url", "squadra", "team_slug"] if column in quotazioni.columns]
        rows = quotazioni[selected].dropna(subset=["nome", "url"]).to_dict("records")
        stats: dict[str, pd.DataFrame] = {}

        def worker(row: Mapping[str, Any]) -> tuple[str, pd.DataFrame]:
            name = str(row["nome"])
            base_df = baseline.get(name, pd.DataFrame(columns=PLAYER_MATCH_COLUMNS))
            page_df = self.player_scraper.scrape(str(row["url"]) + '/statistico')
            team = resolve_calendar_team(page_df, row.get("squadra"), calendar, row.get("team_slug"))
            if team and (base_df.empty or base_df.attrs.get("calendar_team_resolved") != team):
                base_df = calendar_records_for_team(calendar, team)
            completed = merge_player_page_into_calendar(base_df, page_df)
            completed.attrs["calendar_team_resolved"] = team or base_df.attrs.get("calendar_team_resolved")
            completed.attrs["quotation_team"] = row.get("squadra")
            completed.attrs["quotation_team_slug"] = row.get("team_slug")
            return name, completed

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            for name, df in pool.map(worker, rows):
                stats[name] = df
        return stats

    def run(self, force: bool = False) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        quotazioni = self.load_or_scrape_quotazioni(force=force)
        stats = self.load_or_scrape_stats(quotazioni, force=force)
        return quotazioni, stats


def run(
    reference_year: int,
    *,
    cache_dir: str | Path = "cache",
    proxies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
    max_workers: int = 10,
    force: bool = False,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    config = ScraperConfig(
        reference_year=reference_year,
        cache_dir=cache_dir,
        proxies=proxies,
        headers=headers or dict(DEFAULT_HEADERS),
        timeout=timeout,
        verify=verify,
        max_workers=max_workers,
    )
    return FantacalcioRunner(config).run(force=force)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Fantacalcio quotations and player stats.")
    parser.add_argument("year", type=int, help="Reference year, e.g. 2025 -> season 2024-25")
    parser.add_argument("--cache-dir", default="cache", help="Local cache directory")
    parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers for player pages")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument("--force", action="store_true", help="Ignore cache and scrape again")
    parser.add_argument("--no-verify", action="store_true", help="Disable TLS verification")
    parser.add_argument("--proxy", default=None, help="Proxy URL for both http and https")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None
    quotazioni, stats = run(
        args.year,
        cache_dir=args.cache_dir,
        proxies=proxies,
        verify=not args.no_verify,
        timeout=args.timeout,
        max_workers=args.max_workers,
        force=args.force,
    )
    print(f"Done: {len(quotazioni)} quotation rows, {len(stats)} player timelines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
