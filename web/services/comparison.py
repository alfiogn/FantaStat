from __future__ import annotations

from typing import Any

from repositories.player_repository import PlayerRepository
from .summaries import SummaryService
from .timeline import TimelineService


class ComparisonService:
    """Build side-by-side player comparison payloads."""

    METRICS = [
        "current_price",
        "fvm",
        "avg_fantavote",
        "avg_vote",
        "goals",
        "assists",
        "appearances",
        "starts",
    ]

    def __init__(self, player_repo: PlayerRepository):
        self.player_repo = player_repo
        self.timeline_service = TimelineService()
        self.summary_service = SummaryService()

    def compare(self, season: int, player_ids: list[int | str]) -> dict[str, Any]:
        players = []
        for player_id in player_ids:
            doc = self.player_repo.get_player(player_id)
            if not doc:
                continue
            season_doc = doc.get("seasons", {}).get(str(int(season)))
            records = season_doc.get("records", []) if isinstance(season_doc, dict) else []
            players.append(
                {
                    "player_id": doc.get("player_id") or doc.get("_id"),
                    "name": doc.get("name"),
                    "team": doc.get("team_code") or doc.get("team"),
                    "role": doc.get("role"),
                    "summary": self.summary_service.from_season(season_doc),
                    "timeline": self.timeline_service.build(records),
                }
            )

        return {
            "season": int(season),
            "metrics": list(self.METRICS),
            "players": players,
        }
