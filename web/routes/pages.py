from __future__ import annotations

from flask import Blueprint, render_template, request

from .context import quotation_repo

pages_bp = Blueprint("pages", __name__)


def _default_season() -> int | None:
    return quotation_repo.find_latest_season()


@pages_bp.get("/")
def dashboard():
    return render_template("index.html", default_season=_default_season())


@pages_bp.get("/player/<player_id>")
def player_page(player_id: str):
    return render_template("player.html", player_id=player_id, default_season=_default_season())


@pages_bp.get("/compare")
def compare_page():
    ids = request.args.getlist("id")
    return render_template("compare.html", player_ids=ids, default_season=_default_season())


@pages_bp.get("/team/<team_code>")
def team_page(team_code: str):
    return render_template("team.html", team_code=team_code, default_season=_default_season())


@pages_bp.get("/matchday/<int:matchday>")
def matchday_page(matchday: int):
    return render_template("matchday.html", matchday=matchday, default_season=_default_season())
