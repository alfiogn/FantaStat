from __future__ import annotations

from flask import Blueprint, jsonify, request

from .context import (
    calendar_repo,
    comparison_service,
    current_season_service,
    player_repo,
    quotation_repo,
    team_repo,
    timeline_service,
    time_window_service
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
        return int(request.args.get("days", request.args.get("last_n_days", 38)))
    except ValueError:
        return 38

    
def _limit(default: int = 250, maximum: int = 5000) -> int:
    try:
        value = int(request.args.get("limit", default))
    except ValueError:
        value = default
    return max(1, min(value, maximum))


def _with_last_n_metrics(row: dict, season: int, last_n: int) -> dict:
    player_id = row.get("player_id")
    if player_id is None:
        return row

    records = player_repo.get_player_records(player_id, season)
    valid = [r for r in records if isinstance(r.get("matchday") or r.get("giornata"), int)]
    valid = sorted(valid, key=lambda r: int(r.get("matchday") or r.get("giornata")))
    if last_n > 0:
        valid = valid[-last_n:]

    def num(value):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None

    def total(field):
        return sum(v for v in (num(r.get(field)) for r in valid) if v is not None)

    def avg(field):
        values = [v for v in (num(r.get(field)) for r in valid) if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    enriched = dict(row)
    enriched["last_n_matchdays"] = last_n
    enriched["last_n_records"] = len(valid)
    enriched["last_n_avg_vote"] = avg("voto")
    enriched["last_n_avg_fantavote"] = avg("fantavoto")
    enriched["last_n_goals"] = total("scoredGoals")
    enriched["last_n_assists"] = total("assists")
    enriched["last_n_yellow_cards"] = total("yellowCards")
    enriched["last_n_red_cards"] = total("redCards")
    enriched["last_n_last_matchday"] = max(
        [int(r.get("matchday") or r.get("giornata")) for r in valid],
        default=None,
    )
    return enriched


@api_bp.get("/seasons")
def seasons():
    return jsonify(quotation_repo.seasons())


@api_bp.get("/time-window")
def time_window():
    season = _season()
    days = _days()
    return jsonify(time_window_service.context(season, days))


@api_bp.get("/quotations")
def quotations():
    season = _season()
    days = _days()
    last_n = int(request.args.get("last_n_matchdays", 38))
    rows = quotation_repo.list_quotations(
        season,
        role=request.args.get("role") or None,
        team=request.args.get("team") or None,
        search=request.args.get("search") or None,
        sort=request.args.get("sort", "FVM"),
        direction=-1 if request.args.get("direction", "desc") == "desc" else 1,
        limit=_limit(),
    )
    rows = [time_window_service.enrich_quotation_row(row, season, days) for row in rows]
    return jsonify({"season": season, "days": days, "window": time_window_service.context(season, days), "rows": rows})


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
    payload = time_window_service.player_payload(player_id, season, days)
    if not payload.get("player"):
        return jsonify({"error": "player not found"}), 404
    return jsonify(payload)


@api_bp.get("/player/<player_id>/timeline")
def player_timeline(player_id: str):
    season = _season()
    days = _days()
    records = time_window_service.window_records(player_id, season, days)
    return jsonify({"season": season, "timeline": timeline_service.build(records)})


@api_bp.get("/compare")
def compare():
    season = _season()
    ids = request.args.getlist("id") or request.args.getlist("player_id")
    return jsonify(comparison_service.compare(season, ids))


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
    return jsonify({"season": season, "matchday": matchday, "matches": calendar_repo.get_matchday(season, matchday)})


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
