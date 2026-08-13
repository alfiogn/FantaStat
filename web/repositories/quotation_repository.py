from __future__ import annotations

import re
from typing import Any

from .database import Database


class QuotationRepository:
    """Read access to the flattened quotation table."""

    def __init__(self, database: Database):
        self.col = database.collection("quotation_rows")

    def seasons(self) -> list[int]:
        values = [v for v in self.col.distinct("season") if isinstance(v, int)]
        return sorted(values, reverse=True)

    def find_latest_season(self) -> int | None:
        values = self.seasons()
        return values[0] if values else None

    def list_quotations(
        self,
        season: int,
        *,
        role: str | None = None,
        team: str | None = None,
        search: str | None = None,
        sort: str = "FVM",
        direction: int = -1,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"season": int(season)}
        if role:
            query["role"] = role
        if team:
            query["team"] = team
        if search:
            query["name"] = {"$regex": re.escape(search), "$options": "i"}

        projection = {"_id": 0}
        cursor = self.col.find(query, projection).sort(sort, direction).limit(int(limit))
        return list(cursor)

    def get_player_quotation(self, season: int, player_id: int | str) -> dict[str, Any] | None:
        query = {"season": int(season), "player_id": self._coerce_player_id(player_id)}
        return self.col.find_one(query, {"_id": 0})

    def top_fvm(self, season: int, limit: int = 20) -> list[dict[str, Any]]:
        return list(
            self.col.find({"season": int(season)}, {"_id": 0})
            .sort("FVM", -1)
            .limit(int(limit))
        )

    def top_quotation(self, season: int, limit: int = 20) -> list[dict[str, Any]]:
        return list(
            self.col.find({"season": int(season)}, {"_id": 0})
            .sort("QA", -1)
            .limit(int(limit))
        )

    def teams(self, season: int) -> list[str]:
        return sorted(x for x in self.col.distinct("team", {"season": int(season)}) if x)

    def roles(self, season: int) -> list[str]:
        order = {"P": 0, "D": 1, "C": 2, "A": 3}
        values = [x for x in self.col.distinct("role", {"season": int(season)}) if x]
        return sorted(values, key=lambda x: order.get(str(x), 99))

    @staticmethod
    def _coerce_player_id(value: int | str) -> int | str:
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)
