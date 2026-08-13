from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from repositories.calendar_repository import CalendarRepository
from repositories.player_repository import PlayerRepository
from repositories.quotation_repository import QuotationRepository


class TimeWindowService:
    """Global calendar-date window used by dashboard, player and comparison.

    The anchor date is the most recent meaningful calendar date:
    - prefer FINISHED calendar matches
    - otherwise fall back to the most recent dated calendar match

    The window is [anchor_date - N days, anchor_date].
    Stats are recomputed from player records whose match_date falls in this window.
    """

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        player_repo: PlayerRepository,
        quotation_repo: QuotationRepository,
    ):
        self.calendar_repo = calendar_repo
        self.player_repo = player_repo
        self.quotation_repo = quotation_repo

    def context(self, season: int, days: int = 38) -> dict[str, Any]:
        anchor = self.anchor_date(season)
        if anchor is None:
            return {
                "season": int(season),
                "days": int(days),
                "anchor_date": None,
                "start_date": None,
                "end_date": None,
                "has_window": False,
            }
        start = anchor - timedelta(days=int(days))
        return {
            "season": int(season),
            "days": int(days),
            "anchor_date": self._iso(anchor),
            "start_date": self._iso(start),
            "end_date": self._iso(anchor),
            "has_window": True,
        }

    def anchor_date(self, season: int) -> datetime | None:
        matchdays = self.calendar_repo.list_matchdays(season)
        matches: list[dict[str, Any]] = []
        for matchday in matchdays:
            matches.extend(self.calendar_repo.get_matchday(season, matchday))

        finished = [m for m in matches if self._is_finished(m) and self._date(m)]
        dated = [m for m in matches if self._date(m)]
        source = finished or dated
        if not source:
            return None
        return max(self._date(m) for m in source if self._date(m) is not None)

    def enrich_quotation_row(self, row: dict[str, Any], season: int, days: int = 38) -> dict[str, Any]:
        ctx = self.context(season, days)
        out = dict(row)
        out["window"] = ctx

        player_id = row.get("player_id")
        if player_id is None or not ctx["has_window"]:
            out.update(self._empty_metrics(days))
            return out

        records = self.window_records(player_id, season, days)
        out.update(self.metrics_from_records(records, row, days))
        return out

    def player_payload(self, player_id: int | str, season: int, days: int = 38) -> dict[str, Any]:
        player = self.player_repo.get_player(player_id)
        season_doc = self.player_repo.get_player_season(player_id, season)
        records = self.window_records(player_id, season, days)
        quotation = None
        if player:
            pid = player.get("player_id") or player_id
            quotation = self.quotation_repo.get_player_quotation(season, pid)
        return {
            "player": player,
            "season": int(season),
            "days": int(days),
            "window": self.context(season, days),
            "season_data": season_doc,
            "records": records,
            "summary": self.metrics_from_records(records, quotation or {}, days),
        }

    def window_records(self, player_id: int | str, season: int, days: int = 38) -> list[dict[str, Any]]:
        ctx = self.context(season, days)
        if not ctx["has_window"]:
            return []
        start = self._parse(ctx["start_date"])
        end = self._parse(ctx["end_date"])
        records = self.player_repo.get_player_records(player_id, season)
        out = []
        for record in records:
            date = self._date(record)
            if date is None:
                continue
            if start <= date <= end:
                out.append(record)
        return sorted(out, key=lambda r: self._date(r) or datetime.min.replace(tzinfo=timezone.utc))

    def metrics_from_records(
        self,
        records: list[dict[str, Any]],
        quotation: dict[str, Any] | None,
        days: int,
    ) -> dict[str, Any]:
        quotation = quotation or {}
        first_price = self._first_number(records, "quotazione_classic")
        last_price = self._last_number(records, "quotazione_classic")

        qi = first_price
        if qi is None:
            qi = self._number(quotation.get("QI") or quotation.get("initial_quotation"))

        qa = last_price
        if qa is None:
            qa = self._number(quotation.get("QA") or quotation.get("current_quotation") or quotation.get("quotation"))

        fvm = self._number(quotation.get("FVM") or quotation.get("fvm"))

        return {
            "window_days": int(days),
            "window_records": len(records),
            "window_QI": qi,
            "window_QA": qa,
            "window_quotation_delta": self._delta(qa, qi),
            "window_FV": self._avg(records, "fantavoto"),
            "window_MV": self._avg(records, "voto"),
            "window_FVM": fvm,
            "window_goals": self._sum(records, "scoredGoals"),
            "window_assists": self._sum(records, "assists"),
            "window_yellow_cards": self._sum(records, "yellowCards"),
            "window_red_cards": self._sum(records, "redCards"),
            "window_last_matchday": max(
                [int(r.get("matchday") or r.get("giornata")) for r in records if r.get("matchday") or r.get("giornata")],
                default=None,
            ),
        }

    @staticmethod
    def _empty_metrics(days: int) -> dict[str, Any]:
        return {
            "window_days": int(days),
            "window_records": 0,
            "window_QI": None,
            "window_QA": None,
            "window_quotation_delta": None,
            "window_FV": None,
            "window_MV": None,
            "window_FVM": None,
            "window_goals": 0,
            "window_assists": 0,
            "window_yellow_cards": 0,
            "window_red_cards": 0,
            "window_last_matchday": None,
        }

    @classmethod
    def _date(cls, row: dict[str, Any]) -> datetime | None:
        return cls._parse(row.get("match_date") or row.get("date"))

    @staticmethod
    def _is_finished(row: dict[str, Any]) -> bool:
        status = row.get("calendar_match_status") or row.get("status")
        return str(status or "").upper() == "FINISHED"

    @staticmethod
    def _parse(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _number(value: Any) -> int | float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            number = float(str(value).replace(",", "."))
        except ValueError:
            return None
        return int(number) if number.is_integer() else number

    @classmethod
    def _sum(cls, records: list[dict[str, Any]], field: str) -> int | float:
        return sum(v for v in (cls._number(r.get(field)) for r in records) if v is not None)

    @classmethod
    def _avg(cls, records: list[dict[str, Any]], field: str) -> float | None:
        values = [v for v in (cls._number(r.get(field)) for r in records) if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    @classmethod
    def _first_number(cls, records: list[dict[str, Any]], field: str) -> int | float | None:
        for record in records:
            value = cls._number(record.get(field))
            if value is not None:
                return value
        return None

    @classmethod
    def _last_number(cls, records: list[dict[str, Any]], field: str) -> int | float | None:
        for record in reversed(records):
            value = cls._number(record.get(field))
            if value is not None:
                return value
        return None

    @staticmethod
    def _delta(current: int | float | None, initial: int | float | None) -> int | float | None:
        if current is None or initial is None:
            return None
        return current - initial
