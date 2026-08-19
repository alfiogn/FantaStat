from __future__ import annotations

from typing import Any


class SummaryService:
    """Extract safe summary blocks from player season documents."""

    EMPTY = {
        "records": 0,
        "appearances": 0,
        "starts": 0,
        "sub_ins": 0,
        "last_matchday": None,
        "avg_vote": None,
        "avg_fantavote": None,
        "goals": 0,
        "assists": 0,
        "yellow_cards": 0,
        "red_cards": 0,
        "current_price": None,
        "fvm": None,
    }

    def from_season(self, season_doc: dict[str, Any] | None) -> dict[str, Any]:
        if not season_doc:
            return dict(self.EMPTY)
        summary = season_doc.get("summary")
        if not isinstance(summary, dict):
            return dict(self.EMPTY)
        out = dict(self.EMPTY)
        out.update(summary)
        return out
