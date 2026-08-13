from __future__ import annotations

import re
from typing import Any

from .database import Database


class PlayerRepository:
    def __init__(self, database: Database):
        self.col = database.collection("players")

    def get_player(self, player_id: int | str) -> dict[str, Any] | None:
        try:
            pid = int(player_id)
            doc = self.col.find_one({"player_id": pid}, {"_id": 0})
            if doc:
                return doc
        except (TypeError, ValueError):
            pass
        return self.col.find_one({"_id": str(player_id)}, {"_id": 0})

    def get_player_season(self, player_id: int | str, season: int) -> dict[str, Any] | None:
        doc = self.get_player(player_id)
        if not doc:
            return None
        seasons = doc.get("seasons", {})
        return seasons.get(str(int(season))) if isinstance(seasons, dict) else None

    def get_player_records(self, player_id: int | str, season: int) -> list[dict[str, Any]]:
        season_doc = self.get_player_season(player_id, season)
        if not season_doc:
            return []
        records = season_doc.get("records", [])
        return records if isinstance(records, list) else []

    def search_players(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return list(self.col.find({"name": {"$regex": re.escape(query), "$options": "i"}}, {"_id": 0, "player_id": 1, "name": 1, "team": 1, "team_code": 1, "role": 1}).limit(int(limit)))
