from __future__ import annotations

import re
from typing import Any

from .database import Database


class CalendarRepository:
    TEAM_ALIASES = {
        "ATA": ["Atalanta"],
        "BOL": ["Bologna"],
        "CAG": ["Cagliari"],
        "COM": ["Como"],
        "CRE": ["Cremonese"],
        "EMP": ["Empoli"],
        "FIO": ["Fiorentina"],
        "FRO": ["Frosinone"],
        "GEN": ["Genoa"],
        "INT": ["Inter", "Internazionale"],
        "JUV": ["Juventus"],
        "LAZ": ["Lazio"],
        "LEC": ["Lecce"],
        "MIL": ["Milan"],
        "MON": ["Monza"],
        "NAP": ["Napoli"],
        "PAR": ["Parma"],
        "PIS": ["Pisa"],
        "ROM": ["Roma"],
        "SAS": ["Sassuolo"],
        "TOR": ["Torino"],
        "UDI": ["Udinese"],
        "VEN": ["Venezia"],
        "VER": ["Verona", "Hellas Verona"],
    }

    def __init__(self, database: Database):
        # Current DB sample uses the legacy grouped collection.
        self.col = database.collection("calendars")

    def list_matchdays(self, season: int) -> list:
        return sorted(
            [
                value
                for value in self.col.distinct("giornata", {"year": int(season)})
                if isinstance(value, int)
            ]
        )

    def get_matchday(
        self,
        season: int,
        matchday: int,
    ) -> list[dict[str, Any]]:
        doc = self.col.find_one(
            {
                "year": int(season),
                "giornata": int(matchday),
            },
            {"_id": 0, "matches": 1},
        )

        if not doc:
            return []

        matches = doc.get("matches", [])
        if not isinstance(matches, list):
            return []

        return sorted(
            [
                self._normalise_match(match, int(season), int(matchday))
                for match in matches
                if isinstance(match, dict)
            ],
            key=lambda row: str(row.get("match_date") or ""),
        )

    def team_fixtures(
        self,
        season: int,
        team: str,
    ) -> list[dict[str, Any]]:
        terms = self._terms(team)
        fixtures = []

        for matchday in self.list_matchdays(season):
            for match in self.get_matchday(season, matchday):
                home = self._norm(match.get("home_team") or match.get("team_home"))
                away = self._norm(match.get("away_team") or match.get("team_away"))

                if home in terms or away in terms:
                    fixtures.append(match)

        return fixtures

    def next_team_fixtures(
        self,
        season: int,
        team: str,
        *,
        after_matchday: int = 0,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        return [
            fixture
            for fixture in self.team_fixtures(season, team)
            if int(fixture.get("matchday") or fixture.get("giornata") or 0) > int(after_matchday)
        ][: int(limit)]

    def _normalise_match(
        self,
        match: dict[str, Any],
        season: int,
        matchday: int,
    ) -> dict[str, Any]:
        out = dict(match)

        out.setdefault("season", season)
        out.setdefault("year", season)
        out.setdefault("matchday", matchday)
        out.setdefault("giornata", matchday)

        out.setdefault("home_team", out.get("team_home"))
        out.setdefault("away_team", out.get("team_away"))

        status = out.get("calendar_match_status") or out.get("status")
        out.setdefault("played", str(status or "").upper() == "FINISHED")

        return out

    def _terms(self, team: str) -> set:
        values = [team] + self.TEAM_ALIASES.get(str(team or "").upper(), [])
        return {self._norm(value) for value in values if value}

    @staticmethod
    def _norm(value: Any) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            " ",
            str(value or "").casefold(),
        ).strip()