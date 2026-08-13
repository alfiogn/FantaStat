from __future__ import annotations

from typing import Any


class TimelineService:
    """Transform raw player records into chart-ready series."""

    def build(self, records: list[dict[str, Any]]) -> dict[str, list[Any]]:
        ordered = sorted(
            [r for r in records if r.get("matchday") or r.get("giornata")],
            key=lambda r: int(r.get("matchday") or r.get("giornata")),
        )

        matchdays: list[int] = []
        voto: list[float | None] = []
        fantavoto: list[float | None] = []
        quotation: list[float | int | None] = []
        status: list[str | None] = []
        match_text: list[str | None] = []
        goals_cumulative: list[int | float] = []
        assists_cumulative: list[int | float] = []

        goals_total = 0
        assists_total = 0

        for row in ordered:
            matchday = int(row.get("matchday") or row.get("giornata"))
            goals_total += self._number(row.get("scoredGoals")) or 0
            assists_total += self._number(row.get("assists")) or 0

            matchdays.append(matchday)
            voto.append(self._number(row.get("voto")))
            fantavoto.append(self._number(row.get("fantavoto")))
            quotation.append(self._number(row.get("quotazione_classic")))
            status.append(row.get("status"))
            match_text.append(row.get("match_text"))
            goals_cumulative.append(goals_total)
            assists_cumulative.append(assists_total)

        return {
            "matchdays": matchdays,
            "voto": voto,
            "fantavoto": fantavoto,
            "quotation": quotation,
            "status": status,
            "match_text": match_text,
            "goals_cumulative": goals_cumulative,
            "assists_cumulative": assists_cumulative,
        }

    @staticmethod
    def _number(value: Any) -> int | float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            return None
