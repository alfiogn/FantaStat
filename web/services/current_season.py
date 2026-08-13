from __future__ import annotations

from typing import Any
from repositories.calendar_repository import CalendarRepository
from repositories.player_repository import PlayerRepository
from repositories.quotation_repository import QuotationRepository


class CurrentSeasonService:
    def __init__(self, calendar_repo: CalendarRepository, player_repo: PlayerRepository, quotation_repo: QuotationRepository | None = None):
        self.calendar_repo = calendar_repo
        self.player_repo = player_repo
        self.quotation_repo = quotation_repo

    def status(self, season: int, sample_player_id: int | str | None = None) -> dict[str, Any]:
        calendar_days = self.calendar_repo.list_matchdays(season)
        player_days = self.available_player_matchdays(season, sample_player_id)
        return {
            "season": int(season), "calendar_matchdays": calendar_days, "available_player_matchdays": player_days,
            "missing_player_matchdays": [d for d in calendar_days if d not in set(player_days)],
            "last_calendar_matchday": max(calendar_days) if calendar_days else None,
            "last_known_player_matchday": max(player_days) if player_days else None,
            "is_partial": bool(calendar_days and (not player_days or max(player_days) < max(calendar_days))),
        }

    def player_status(self, player_id: int | str, season: int) -> dict[str, Any]:
        status = self.status(season, player_id)
        player = self.player_repo.get_player(player_id) or {}
        team = player.get("team_code") or player.get("team")
        status.update({"player_id": player.get("player_id") or player_id, "player_name": player.get("name"), "team": team, "next_fixtures": []})
        if team:
            status["next_fixtures"] = self.calendar_repo.next_team_fixtures(season, team, after_matchday=status.get("last_known_player_matchday") or 0, limit=5)
        return status

    def available_player_matchdays(self, season: int, sample_player_id: int | str | None = None) -> list[int]:
        if sample_player_id is None and self.quotation_repo is not None:
            top = self.quotation_repo.top_fvm(season, 1)
            if top: sample_player_id = top[0].get("player_id")
        if sample_player_id is None: return []
        days = set()
        for r in self.player_repo.get_player_records(sample_player_id, season):
            d = r.get("matchday") or r.get("giornata")
            if isinstance(d, int): days.add(d)
        return sorted(days)
