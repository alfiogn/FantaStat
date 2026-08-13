from __future__ import annotations

from typing import Any

from repositories.calendar_repository import CalendarRepository
from repositories.player_repository import PlayerRepository
from repositories.quotation_repository import QuotationRepository


class CurrentSeasonService:
    """Current/partial season utilities.

    A season is considered partial when the calendar has future matchdays or
    when player timelines do not cover all calendar matchdays. This is normal
    for the current season and must never be treated as a data integrity error.
    """

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        player_repo: PlayerRepository,
        quotation_repo: QuotationRepository | None = None,
    ):
        self.calendar_repo = calendar_repo
        self.player_repo = player_repo
        self.quotation_repo = quotation_repo

    def status(self, season: int, sample_player_id: int | str | None = None) -> dict[str, Any]:
        calendar_days = self.calendar_repo.list_matchdays(season)
        player_days = self.available_player_matchdays(season, sample_player_id)

        last_calendar = max(calendar_days) if calendar_days else None
        last_player = max(player_days) if player_days else None

        return {
            "season": int(season),
            "calendar_matchdays": calendar_days,
            "available_player_matchdays": player_days,
            "missing_player_matchdays": self._missing(calendar_days, player_days),
            "last_calendar_matchday": last_calendar,
            "last_known_player_matchday": last_player,
            "is_partial": bool(last_calendar and (last_player is None or last_player < last_calendar)),
            "has_calendar": bool(calendar_days),
            "has_player_data": bool(player_days),
        }

    def player_status(self, player_id: int | str, season: int) -> dict[str, Any]:
        status = self.status(season, sample_player_id=player_id)
        player = self.player_repo.get_player(player_id) or {}
        team = player.get("team_code") or player.get("team")
        status["player_id"] = player.get("player_id") or player_id
        status["player_name"] = player.get("name")
        status["team"] = team
        status["next_fixtures"] = []
        if team:
            status["next_fixtures"] = self.calendar_repo.next_team_fixtures(
                season,
                team,
                after_matchday=status.get("last_known_player_matchday") or 0,
                limit=5,
            )
        return status

    def available_player_matchdays(self, season: int, sample_player_id: int | str | None = None) -> list[int]:
        if sample_player_id is None and self.quotation_repo is not None:
            top = self.quotation_repo.top_fvm(season, limit=1)
            if top:
                sample_player_id = top[0].get("player_id")

        if sample_player_id is None:
            return []

        days: set[int] = set()
        records = self.player_repo.get_player_records(sample_player_id, season)
        for row in records:
            day = row.get("matchday") or row.get("giornata")
            if isinstance(day, int):
                days.add(day)
        return sorted(days)

    @staticmethod
    def _missing(calendar_days: list[int], available_days: list[int]) -> list[int]:
        available = set(available_days)
        return [day for day in calendar_days if day not in available]
