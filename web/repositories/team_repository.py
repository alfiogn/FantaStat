from __future__ import annotations

from typing import Any

from .database import Database


class TeamRepository:
    """Read access to season teams."""

    def __init__(self, database: Database):
        self.col = database.collection("teams")

    def list_teams(self, season: int) -> list[dict[str, Any]]:
        return list(
            self.col.find({"season": int(season)}, {"_id": 0})
            .sort("team_code", 1)
        )

    def get_team(self, season: int, team_code: str) -> dict[str, Any] | None:
        return self.col.find_one(
            {"season": int(season), "team_code": team_code},
            {"_id": 0},
        )
