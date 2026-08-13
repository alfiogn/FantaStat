from __future__ import annotations

from typing import Any


class TimelineService:
    def build(self, records: list[dict[str, Any]]) -> dict[str, list[Any]]:
        ordered = sorted([r for r in records if r.get("matchday") or r.get("giornata")], key=lambda r: int(r.get("matchday") or r.get("giornata")))
        goals = 0
        assists = 0
        out = {"matchdays": [], "voto": [], "fantavoto": [], "quotation": [], "status": [], "match_text": [], "goals_cumulative": [], "assists_cumulative": []}
        for r in ordered:
            goals += self._num(r.get("scoredGoals")) or 0
            assists += self._num(r.get("assists")) or 0
            out["matchdays"].append(int(r.get("matchday") or r.get("giornata")))
            out["voto"].append(self._num(r.get("voto")))
            out["fantavoto"].append(self._num(r.get("fantavoto")))
            out["quotation"].append(self._num(r.get("quotazione_classic")))
            out["status"].append(r.get("status"))
            out["match_text"].append(r.get("match_text"))
            out["goals_cumulative"].append(goals)
            out["assists_cumulative"].append(assists)
        return out

    @staticmethod
    def _num(v: Any) -> int | float | None:
        if v is None or isinstance(v, bool): return None
        if isinstance(v, (int, float)): return v
        try: return float(str(v).replace(",", "."))
        except ValueError: return None
