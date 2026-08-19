from __future__ import annotations

import re
from typing import Any

from .database import Database


class QuotationRepository:
    def __init__(self, database: Database):
        self.col = database.collection("quotations")

    def seasons(self) -> list:
        return sorted(
            [v for v in self.col.distinct("year") if isinstance(v, int)],
            reverse=True,
        )

    def find_latest_season(self) -> int | None:
        seasons = self.seasons()
        return seasons[0] if seasons else None

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
        rows = self._season_rows(season)

        if role:
            rows = [row for row in rows if row.get("role") == role or row.get("ruolo") == role]

        if team:
            rows = [row for row in rows if row.get("team") == team or row.get("squadra") == team]

        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            rows = [
                row for row in rows
                if pattern.search(str(row.get("name") or row.get("nome") or ""))
            ]

        rows.sort(
            key=lambda row: self._sort_value(row, sort),
            reverse=(direction == -1),
        )

        return rows[: int(limit)]

    def get_player_quotation(
        self,
        season: int,
        player_id: int | str,
    ) -> dict[str, Any] | None:
        try:
            wanted_int = int(player_id)
        except (TypeError, ValueError):
            wanted_int = None

        wanted_str = str(player_id)

        for row in self._season_rows(season):
            candidates = {
                str(row.get("player_id") or ""),
                str(row.get("fantacalcio_id") or ""),
                str(row.get("player_slug") or ""),
            }

            if wanted_int is not None:
                if row.get("player_id") == wanted_int:
                    return row
                if row.get("fantacalcio_id") == wanted_int:
                    return row

            if wanted_str in candidates:
                return row

        return None

    def top_fvm(self, season: int, limit: int = 20) -> list[dict[str, Any]]:
        return self.list_quotations(
            season,
            sort="FVM",
            direction=-1,
            limit=limit,
        )

    def teams(self, season: int) -> list:
        return sorted(
            {
                row.get("team") or row.get("squadra")
                for row in self._season_rows(season)
                if row.get("team") or row.get("squadra")
            }
        )

    def roles(self, season: int) -> list:
        order = {"P": 0, "D": 1, "C": 2, "A": 3}
        return sorted(
            {
                row.get("role") or row.get("ruolo")
                for row in self._season_rows(season)
                if row.get("role") or row.get("ruolo")
            },
            key=lambda value: order.get(str(value), 99),
        )

    def _season_rows(self, season: int) -> list[dict[str, Any]]:
        doc = self.col.find_one(
            {"year": int(season)},
            {"_id": 0, "year": 1, "quotations": 1},
        )

        if not doc:
            return []

        rows = doc.get("quotations", [])
        if not isinstance(rows, list):
            return []

        return [
            self._normalise_row(row, int(season))
            for row in rows
            if isinstance(row, dict)
        ]

    def _normalise_row(self, row: dict[str, Any], season: int) -> dict[str, Any]:
        out = dict(row)

        url_player_id = self._id_from_url(out.get("url"))

        player_id = out.get("player_id")
        if player_id is None:
            player_id = url_player_id

        name = out.get("nome") or out.get("name")
        team = out.get("squadra") or out.get("team")
        role = out.get("ruolo") or out.get("role")

        out.update(
            {
                "season": int(season),
                "year": int(season),

                "name": name,
                "nome": name,

                "team": team,
                "squadra": team,

                "role": role,
                "ruolo": role,

                # This must be integer when available.
                "player_id": player_id,

                # Optional debug/fallback fields.
                "fantacalcio_id": url_player_id,
                "player_slug": self._slug(name),
            }
        )

        return out

    @staticmethod
    def _sort_value(row: dict[str, Any], sort: str) -> Any:
        aliases = {
            "name": "name",
            "team": "team",
            "role": "role",
            "QA": "QA",
            "QI": "QI",
            "FVM": "FVM",
            "quotation_delta": "quotation_delta",
        }
        key = aliases.get(sort, sort)
        value = row.get(key)
        if value is None:
            return "" if key in {"name", "team", "role"} else -10**18
        return value

    @staticmethod
    def _id_from_url(value: Any) -> int | None:
        if not isinstance(value, str):
            return None

        match = re.search(r"/(\d+)(?:/)?$", value.rstrip("/"))
        return int(match.group(1)) if match else None


    @classmethod
    def _slug(cls, value: Any) -> str:
        text = str(value or "").casefold().strip()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")