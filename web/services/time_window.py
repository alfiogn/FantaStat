from __future__ import annotations

from collections import defaultdict
from typing import Any

from repositories.calendar_repository import CalendarRepository
from repositories.player_repository import PlayerRepository
from repositories.quotation_repository import QuotationRepository


class TimeWindowService:
    """Rolling *fantasy matchday* window across seasons.

    Despite the UI label "Last days", the unit is Fantacalcio/Serie A matchday
    (giornata), not calendar date.

    Example before 2027 has started:
        selected season = 2027
        latest meaningful matchday in 2027 = None
        requested days = 38

    The window is:
        2026 matchdays 1..38

    Example after 2027 matchday 1 is played:
        selected season = 2027
        latest meaningful matchday in 2027 = 1
        requested days = 38

    The window is:
        2026 matchdays 2..38 + 2027 matchday 1

    Meaningful current-season matchdays are derived from the calendar collection:
    a matchday is meaningful only if at least one fixture is FINISHED. Calendar-only
    future matchdays contribute zero records to the rolling window.
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
        pairs = self.window_matchdays(season, days)
        start = pairs[0] if pairs else None
        end = pairs[-1] if pairs else None
        return {
            "season": int(season),
            "days": int(days),
            "unit": "matchdays",
            "has_window": bool(pairs),
            "start": start,
            "end": end,
            "start_label": self._label(start),
            "end_label": self._label(end),
            "matchdays": pairs,
            "seasons": sorted({p["season"] for p in pairs}),
        }

    def window_matchdays(self, season: int, days: int = 38) -> list[dict[str, int]]:
        season = int(season)
        days = max(1, int(days))
        seasons = self._known_seasons()
        if season not in seasons:
            seasons.append(season)
            seasons = sorted(set(seasons), reverse=True)

        selected_index = seasons.index(season)
        collected: list[dict[str, int]] = []

        for year in seasons[selected_index:]:
            latest = self.latest_meaningful_matchday(year)
            if latest is None:
                continue

            # For the selected season, start from the latest meaningful day.
            # For prior seasons, latest is usually 38.
            for matchday in range(latest, 0, -1):
                collected.append({"season": int(year), "matchday": int(matchday)})
                if len(collected) >= days:
                    break
            if len(collected) >= days:
                break

        # collected was newest -> oldest. Return chronological oldest -> newest.
        return list(reversed(collected))

    def latest_meaningful_matchday(self, season: int) -> int | None:
        """Return the latest actually played matchday for a season.

        Important current-season rule:
        if the selected/current season has only calendar rows but no FINISHED
        fixtures yet, it contributes zero matchdays to the rolling window.

        Example on auction day before 2027 starts:
            selected season = 2027
            latest_meaningful_matchday(2027) = None
            last 38 = 2026 MD1..MD38

        After 2027 MD1 is played:
            latest_meaningful_matchday(2027) = 1
            last 38 = 2026 MD2..MD38 + 2027 MD1
        """
        matchdays = self.calendar_repo.list_matchdays(season)
        if not matchdays:
            return None

        meaningful: list[int] = []
        for matchday in matchdays:
            fixtures = self.calendar_repo.get_matchday(season, matchday)
            if any(self._is_finished(match) for match in fixtures):
                meaningful.append(matchday)

        return max(meaningful) if meaningful else None

    def enrich_quotation_row(self, row: dict[str, Any], season: int, days: int = 38) -> dict[str, Any]:
        out = dict(row)
        out["window"] = self.context(season, days)

        player_id = row.get("player_id")
        records = self.window_records(player_id, season, days) if player_id is not None else []
        out.update(self.metrics_from_records(records, row, days))
        return out

    def player_payload(self, player_id: int | str, season: int, days: int = 38) -> dict[str, Any]:
        player = self.player_repo.get_player(player_id)
        season_doc = self.player_repo.get_player_season(player_id, season)
        records = self.window_records(player_id, season, days)
        quotation = None
        if player:
            quotation = self.quotation_repo.get_player_quotation(
                season,
                player.get("player_id") or player_id,
            )
        return {
            "player": player,
            "season": int(season),
            "days": int(days),
            "unit": "matchdays",
            "window": self.context(season, days),
            "season_data": season_doc,
            "records": records,
            "summary": self.metrics_from_records(records, quotation or {}, days),
        }

    def window_records(self, player_id: int | str, season: int, days: int = 38) -> list[dict[str, Any]]:
        if player_id is None:
            return []

        pairs = self.window_matchdays(season, days)
        wanted = {(p["season"], p["matchday"]) for p in pairs}
        ordered_keys = {(p["season"], p["matchday"]): i for i, p in enumerate(pairs)}

        records: list[dict[str, Any]] = []
        for year in sorted({p["season"] for p in pairs}):
            for record in self.player_repo.get_player_records(player_id, year):
                md = record.get("matchday") or record.get("giornata")
                if not isinstance(md, int):
                    continue
                key = (int(year), int(md))
                if key not in wanted:
                    continue
                enriched = dict(record)
                enriched["window_season"] = int(year)
                enriched["window_matchday"] = int(md)
                enriched["window_index"] = ordered_keys[key]
                records.append(enriched)

        return sorted(records, key=lambda r: r.get("window_index", 0))

    def metrics_from_records(
        self,
        records: list[dict[str, Any]],
        quotation: dict[str, Any] | None,
        days: int,
    ) -> dict[str, Any]:
        quotation = quotation or {}
        qi = self._first_number(records, "quotazione_classic")
        if qi is None:
            qi = self._number(quotation.get("QI") or quotation.get("initial_quotation"))

        qa = self._last_number(records, "quotazione_classic")
        if qa is None:
            qa = self._number(
                quotation.get("QA")
                or quotation.get("current_quotation")
                or quotation.get("quotation")
            )

        first_record = records[0] if records else None
        last_record = records[-1] if records else None

        return {
            "window_days": int(days),
            "window_unit": "matchdays",
            "window_records": len(records),
            "window_QI": qi,
            "window_QA": qa,
            "window_quotation_delta": None if qi is None or qa is None else qa - qi,
            "window_FV": self._avg(records, "fantavoto"),
            "window_MV": self._avg(records, "voto"),
            "window_FVM": self._number(quotation.get("FVM") or quotation.get("fvm")),
            "window_goals": self._sum(records, "scoredGoals"),
            "window_assists": self._sum(records, "assists"),
            "window_yellow_cards": self._sum(records, "yellowCards"),
            "window_red_cards": self._sum(records, "redCards"),
            "window_start_season": first_record.get("window_season") if first_record else None,
            "window_start_matchday": first_record.get("window_matchday") if first_record else None,
            "window_end_season": last_record.get("window_season") if last_record else None,
            "window_end_matchday": last_record.get("window_matchday") if last_record else None,
        }

    def _known_seasons(self) -> list[int]:
        seasons = set(self.quotation_repo.seasons())
        # Include seasons that may exist only in calendar_matches.
        # We do it through matchday discovery over quotation seasons normally; this
        # fallback keeps code simple and avoids adding another repository method.
        return sorted(seasons, reverse=True)

    @staticmethod
    def _is_finished(match: dict[str, Any]) -> bool:
        status = match.get("calendar_match_status") or match.get("status")
        return str(status or "").upper() == "FINISHED"

    @staticmethod
    def _label(pair: dict[str, int] | None) -> str | None:
        if not pair:
            return None
        return f"{pair['season']} MD{pair['matchday']}"

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
