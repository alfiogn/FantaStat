from __future__ import annotations

import re
from typing import Any

from .database import Database


class QuotationRepository:
    def __init__(self, database: Database):
        self.col = database.collection("quotation_rows")

    def seasons(self) -> list[int]:
        return sorted([v for v in self.col.distinct("season") if isinstance(v, int)], reverse=True)

    def find_latest_season(self) -> int | None:
        seasons = self.seasons()
        return seasons[0] if seasons else None

    def list_quotations(self, season: int, *, role: str | None = None, team: str | None = None, search: str | None = None, sort: str = "FVM", direction: int = -1, limit: int = 1000) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"season": int(season)}
        if role:
            query["role"] = role
        if team:
            query["team"] = team
        if search:
            query["name"] = {"$regex": re.escape(search), "$options": "i"}
        return list(self.col.find(query, {"_id": 0}).sort(sort, direction).limit(int(limit)))

    def get_player_quotation(self, season: int, player_id: int | str) -> dict[str, Any] | None:
        try:
            pid: int | str = int(player_id)
        except (TypeError, ValueError):
            pid = str(player_id)
        return self.col.find_one({"season": int(season), "player_id": pid}, {"_id": 0})

    def top_fvm(self, season: int, limit: int = 20) -> list[dict[str, Any]]:
        return list(self.col.find({"season": int(season)}, {"_id": 0}).sort("FVM", -1).limit(int(limit)))

    def teams(self, season: int) -> list[str]:
        return sorted(x for x in self.col.distinct("team", {"season": int(season)}) if x)

    def roles(self, season: int) -> list[str]:
        order = {"P": 0, "D": 1, "C": 2, "A": 3}
        return sorted([x for x in self.col.distinct("role", {"season": int(season)}) if x], key=lambda x: order.get(str(x), 99))
