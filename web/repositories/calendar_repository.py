from __future__ import annotations

import re
from typing import Any

from .database import Database


class CalendarRepository:
    TEAM_ALIASES = {
        "ATA": ["Atalanta"], "BOL": ["Bologna"], "CAG": ["Cagliari"], "COM": ["Como"],
        "CRE": ["Cremonese"], "EMP": ["Empoli"], "FIO": ["Fiorentina"], "FRO": ["Frosinone"],
        "GEN": ["Genoa"], "INT": ["Inter", "Internazionale"], "JUV": ["Juventus"], "LAZ": ["Lazio"],
        "LEC": ["Lecce"], "MIL": ["Milan"], "MON": ["Monza"], "NAP": ["Napoli"], "PAR": ["Parma"],
        "PIS": ["Pisa"], "ROM": ["Roma"], "SAS": ["Sassuolo"], "TOR": ["Torino"], "UDI": ["Udinese"],
        "VEN": ["Venezia"], "VER": ["Verona", "Hellas Verona"],
    }

    def __init__(self, database: Database):
        self.col = database.collection("calendar_matches")

    def list_matchdays(self, season: int) -> list[int]:
        return sorted([x for x in self.col.distinct("matchday", {"season": int(season)}) if isinstance(x, int)])

    def get_matchday(self, season: int, matchday: int) -> list[dict[str, Any]]:
        return list(self.col.find({"season": int(season), "matchday": int(matchday)}, {"_id": 0}).sort("match_date", 1))

    def team_fixtures(self, season: int, team: str) -> list[dict[str, Any]]:
        return list(self.col.find(self._team_query(season, team), {"_id": 0}).sort("matchday", 1))

    def next_team_fixtures(self, season: int, team: str, *, after_matchday: int = 0, limit: int = 5) -> list[dict[str, Any]]:
        query = self._team_query(season, team)
        query["matchday"] = {"$gt": int(after_matchday)}
        return list(self.col.find(query, {"_id": 0}).sort("matchday", 1).limit(int(limit)))

    def _team_query(self, season: int, team: str) -> dict[str, Any]:
        terms = [team] + self.TEAM_ALIASES.get(str(team or "").upper(), [])
        conditions = []
        for field in ("home_team", "away_team", "team_home", "team_away"):
            for term in terms:
                if term:
                    conditions.append({field: term})
                    conditions.append({field: {"$regex": rf"^{re.escape(str(term))}$", "$options": "i"}})
        return {"season": int(season), "$or": conditions or [{"home_team": team}]}
