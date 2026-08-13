from __future__ import annotations

import re
from typing import Any

from .database import Database


class CalendarRepository:
    """Read access to flattened fixtures.

    Team names in calendar files can be full names (Internazionale) while
    quotation rows usually store short codes (INT). For this reason the
    repository accepts several team aliases and performs a pragmatic regex
    fallback when exact matching fails.
    """

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
        self.col = database.collection("calendar_matches")

    def list_matchdays(self, season: int) -> list[int]:
        values = [x for x in self.col.distinct("matchday", {"season": int(season)}) if isinstance(x, int)]
        return sorted(values)

    def get_matchday(self, season: int, matchday: int) -> list[dict[str, Any]]:
        return list(
            self.col.find(
                {"season": int(season), "matchday": int(matchday)},
                {"_id": 0},
            ).sort("match_date", 1)
        )

    def team_fixtures(self, season: int, team: str) -> list[dict[str, Any]]:
        return list(self.col.find(self._team_query(season, team), {"_id": 0}).sort("matchday", 1))

    def next_team_fixtures(
        self,
        season: int,
        team: str,
        *,
        after_matchday: int = 0,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query = self._team_query(season, team)
        query["matchday"] = {"$gt": int(after_matchday)}
        return list(self.col.find(query, {"_id": 0}).sort("matchday", 1).limit(int(limit)))

    def _team_query(self, season: int, team: str) -> dict[str, Any]:
        aliases = self._aliases(team)
        exact_terms = aliases + [team]
        regex_terms = [self._regex_alias(x) for x in exact_terms if x]
        team_conditions: list[dict[str, Any]] = []
        for field in ("home_team", "away_team", "team_home", "team_away"):
            team_conditions.extend({field: value} for value in exact_terms if value)
            team_conditions.extend({field: {"$regex": value, "$options": "i"}} for value in regex_terms if value)
        return {"season": int(season), "$or": team_conditions or [{"home_team": team}]}

    @classmethod
    def _aliases(cls, team: str) -> list[str]:
        key = str(team or "").upper()
        aliases = cls.TEAM_ALIASES.get(key, [])
        return aliases + ([key] if key else [])

    @staticmethod
    def _regex_alias(value: str) -> str:
        return rf"^{re.escape(str(value))}$"
