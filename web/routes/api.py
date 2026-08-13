from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from flask import Blueprint, jsonify, request

from .context import (
    calendar_repo,
    current_season_service,
    quotation_repo,
    team_repo,
    time_window_service,
    window_snapshot_service,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _season() -> int:
    raw = request.args.get("season")
    if raw:
        return int(raw)
    latest = quotation_repo.find_latest_season()
    if latest is None:
        raise ValueError("No season available")
    return latest


def _days() -> int:
    try:
        value = int(request.args.get("days", request.args.get("last_n_days", 38)))
    except ValueError:
        value = 38
    return max(1, value)


def _limit(default: int = 250, maximum: int = 5000) -> int:
    try:
        value = int(request.args.get("limit", default))
    except ValueError:
        value = default
    return max(1, min(value, maximum))


@api_bp.get("/seasons")
def seasons():
    return jsonify(quotation_repo.seasons())


@api_bp.get("/time-window")
def time_window():
    season = _season()
    days = _days()
    return jsonify(time_window_service.context(season, days))


@api_bp.get("/cache/window")
def cache_window_info():
    return jsonify(window_snapshot_service.info())


@api_bp.post("/cache/clear")
def cache_clear():
    window_snapshot_service.clear()
    return jsonify({"status": "cleared"})


@api_bp.get("/quotations")
def quotations():

    t0 = perf_counter()

    season = _season()
    days = _days()

    result = window_snapshot_service.list_rows(
        season,
        days,
        role=request.args.get("role") or None,
        team=request.args.get("team") or None,
        search=request.args.get("search") or None,
        sort=request.args.get("sort", "FVM"),
        direction=-1 if request.args.get("direction", "desc") == "desc" else 1,
        limit=_limit(),
    )

    print(
        f"QUOTATIONS {season=} {days=} "
        f"{len(result['rows'])=} "
        f"elapsed={perf_counter()-t0:.3f}s"
    )

    return jsonify(result)


@api_bp.get("/filters")
def filters():
    season = _season()
    return jsonify(
        {
            "season": season,
            "teams": quotation_repo.teams(season),
            "roles": quotation_repo.roles(season),
        }
    )


@api_bp.get("/player/<player_id>")
def player(player_id: str):
    season = _season()
    days = _days()
    payload = window_snapshot_service.player_payload(player_id, season, days)
    if not payload.get("player"):
        return jsonify({"error": "player not found"}), 404
    return jsonify(payload)


@api_bp.get("/player/<player_id>/timeline")
def player_timeline(player_id: str):
    season = _season()
    days = _days()
    return jsonify(window_snapshot_service.timeline_payload(player_id, season, days))


@api_bp.get("/compare")
def compare():
    season = _season()
    days = _days()
    ids = request.args.getlist("id") or request.args.getlist("player_id")
    return jsonify(window_snapshot_service.compare_payload(season, days, ids))


@api_bp.get("/teams")
def teams():
    season = _season()
    return jsonify({"season": season, "teams": team_repo.list_teams(season)})


@api_bp.get("/team/<team_code>/fixtures")
def team_fixtures(team_code: str):
    season = _season()
    return jsonify({"season": season, "fixtures": calendar_repo.team_fixtures(season, team_code)})


@api_bp.get("/matchday/<int:matchday>")
def matchday(matchday: int):
    season = _season()
    return jsonify(
        {
            "season": season,
            "matchday": matchday,
            "matches": calendar_repo.get_matchday(season, matchday),
        }
    )


@api_bp.get("/player/<player_id>/season-status")
def player_season_status(player_id: str):
    season = _season()
    return jsonify(current_season_service.player_status(player_id, season))


@api_bp.get("/player/<player_id>/fixtures")
def player_fixtures(player_id: str):
    season = _season()
    status = current_season_service.player_status(player_id, season)
    return jsonify({"season": season, "fixtures": status.get("next_fixtures", [])})


@api_bp.get("/season-status")
def season_status():
    season = _season()
    sample = request.args.get("sample_player_id")
    return jsonify(current_season_service.status(season, sample))


@api_bp.get("/lineups")
def lineups():
    season = int(request.args.get("season", 2027))
    path = Path(__file__).resolve().parents[1] / "static" / "data" / f"lineups_{season}.json"
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / "static" / "data" / "lineups_2027.json"
    return jsonify(json.loads(path.read_text(encoding="utf-8")))
