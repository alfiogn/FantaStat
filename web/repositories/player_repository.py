from __future__ import annotations

import re
from typing import Any

from .database import Database


class PlayerRepository:
    """Read access to player identity, summaries and timelines."""

    def __init__(self, database: Database):
        self.col = database.collection("players")

    def get_player(self, player_id: int | str) -> dict[str, Any] | None:
        key = self._coerce_player_id(player_id)
        if isinstance(key, int):
            doc = self.col.find_one({"player_id": key}, {"_id": 0})
            if doc:
                return doc
        return self.col.find_one({"_id": str(player_id)}, {"_id": 0})

    def get_player_by_name(self, name: str) -> dict[str, Any] | None:
        return self.col.find_one({"name": name}, {"_id": 0})

    def search_players(
        self,
        query: str,
        *,
        season: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        q: dict[str, Any] = {"name": {"$regex": re.escape(query), "$options": "i"}}
        projection = {
            "_id": 0,
            "player_id": 1,
            "name": 1,
            "role": 1,
            "team": 1,
            "team_code": 1,
            "team_slug": 1,
        }
        if season is not None:
            projection[f"seasons.{int(season)}.summary"] = 1
        return list(self.col.find(q, projection).limit(int(limit)))

    def get_player_season(self, player_id: int | str, season: int) -> dict[str, Any] | None:
        doc = self.get_player(player_id)
        if not doc:
            return None
        return doc.get("seasons", {}).get(str(int(season)))

    def get_player_records(self, player_id: int | str, season: int) -> list[dict[str, Any]]:
        season_doc = self.get_player_season(player_id, season)
        if not season_doc:
            return []
        records = season_doc.get("records", [])
        return records if isinstance(records, list) else []

    @staticmethod
    def _coerce_player_id(value: int | str) -> int | str:
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)
