from __future__ import annotations

import re
from typing import Any

from .database import Database


class PlayerRepository:
    def __init__(self, database: Database):
        self.col = database.collection("players")

    def get_player(self, player_id: int | str) -> dict[str, Any] | None:
        key = str(player_id)

        queries = [
            {"_id": key},
            {"_id": self._slug(key)},
            {"player_id": key},
        ]

        try:
            queries.append({"player_id": int(player_id)})
        except (TypeError, ValueError):
            pass

        for query in queries:
            doc = self.col.find_one(query, {"_id": 0})
            if doc:
                return self._normalise_player(doc, query)

        return None

    def get_player_season(
        self,
        player_id: int | str,
        season: int,
    ) -> dict[str, Any] | None:
        player = self.get_player(player_id)
        if not player:
            return None

        seasons = player.get("seasons")
        if isinstance(seasons, dict):
            season_doc = seasons.get(str(int(season)))
            if isinstance(season_doc, dict):
                return season_doc

        records = self.get_player_records(player_id, season)

        return {
            "year": int(season),
            "season": int(season),
            "records": records,
            "summary": {},
            "attrs": player.get("attrs", {}),
        }

    def get_player_records(
        self,
        player_id: int | str,
        season: int,
    ) -> list[dict[str, Any]]:
        player = self.get_player(player_id)
        if not player:
            return []

        # New schema support.
        seasons = player.get("seasons")
        if isinstance(seasons, dict):
            season_doc = seasons.get(str(int(season)))
            if isinstance(season_doc, dict):
                records = season_doc.get("records", [])
                return records if isinstance(records, list) else []

        # Legacy schema support: players.stats.records.
        stats = player.get("stats", {})
        records = stats.get("records", []) if isinstance(stats, dict) else []

        if not isinstance(records, list):
            return []

        out = []
        for record in records:
            if not isinstance(record, dict):
                continue

            giornata = record.get("giornata")
            if not isinstance(giornata, int):
                continue

            year_id = record.get("year_id")
            if year_id is not None and str(year_id) != str(int(season)):
                continue

            row = dict(record)
            row.setdefault("season", int(season))
            row.setdefault("year", int(season))
            row.setdefault("matchday", giornata)
            out.append(row)

        return out

    def search_players(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        pattern = {"$regex": re.escape(query), "$options": "i"}

        docs = self.col.find(
            {"name": pattern},
            {"_id": 1, "player_id": 1, "name": 1, "team": 1, "team_code": 1, "role": 1},
        ).limit(int(limit))

        return [self._normalise_player(doc, {}) for doc in docs]

    def _normalise_player(
        self,
        doc: dict[str, Any],
        query: dict[str, Any],
    ) -> dict[str, Any]:
        out = dict(doc)

        raw_id = out.get("player_id")
        mongo_id = out.get("_id")

        if raw_id is not None:
            out.setdefault("id", raw_id)

        if mongo_id is not None:
            out.setdefault("player_key", mongo_id)

        out.setdefault("name", mongo_id or raw_id)

        return out

    @staticmethod
    def _slug(value: Any) -> str:
        text = str(value or "").casefold().strip()
        text = re.sub(r"[^a-z0-9.]+", "_", text)
        return text.strip("_")