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

    def _player_from_quotation(
        self,
        quotation: dict[str, Any],
        requested_id: int | str,
    ) -> dict[str, Any]:
        return {
            "player_id": quotation.get("player_id") or str(requested_id),
            "fantacalcio_id": quotation.get("fantacalcio_id"),
            "name": quotation.get("name") or quotation.get("nome") or str(requested_id),
            "team": quotation.get("team") or quotation.get("squadra"),
            "team_code": quotation.get("team") or quotation.get("squadra"),
            "role": quotation.get("role") or quotation.get("ruolo"),
            "source": "quotation",
        }

    def player_payload(self, player_id: int | str, season: int, days: int = 38) -> dict[str, Any]:
        player = self.player_repo.get_player(player_id)

        quotation = self.quotation_repo.get_player_quotation(
            season,
            player.get("player_id") if player else player_id,
        )

        if not player and quotation:
            player = self._player_from_quotation(quotation, player_id)

        season_doc = None
        records: list[dict[str, Any]] = []

        if player:
            resolved_id = player.get("player_id") or player_id
            season_doc = self.player_repo.get_player_season(resolved_id, season)
            records = self.window_records(resolved_id, season, days)

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
            "window_distributions": self.distributions_from_records(records),
            "window_boxplots": self.boxplots_from_records(records),
        }

    def distributions_from_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Probability distributions over the rolling window.

        Notes:
        - goals use scoredGoals unless ownGoals > 0 and scoredGoals == 0, then value is -ownGoals
        - voto and fantavoto ignore missing values
        - yellow/red cards are binary yes/no
        - result uses win: 1 win, 0 draw, -1 loss
        - status uses raw status label with common ordering
        """
        return {
            "goals": self._integer_distribution(
                [self._goal_bucket(record) for record in records],
                minimum=-1,
            ),
            "assists": self._integer_distribution(
                [self._integer(record.get("assists")) or 0 for record in records],
                minimum=0,
            ),
            "voto": self._half_step_distribution(
                [self._number(record.get("voto")) for record in records],
                start=0,
                stop=10,
            ),
            "fantavoto": self._half_step_distribution(
                [self._number(record.get("fantavoto")) for record in records],
                start=-3,
                stop=15,
            ),
            "yellow_card": self._binary_distribution(
                [bool((self._integer(record.get("yellowCards")) or 0) > 0) for record in records],
                yes_label="Yellow",
                no_label="No yellow",
            ),
            "red_card": self._binary_distribution(
                [bool((self._integer(record.get("redCards")) or 0) > 0) for record in records],
                yes_label="Red",
                no_label="No red",
            ),
            "result": self._categorical_distribution(
                [self._result_label(record.get("win")) for record in records],
                order=["Win", "Draw", "Loss", "Unknown"],
            ),
            "status": self._categorical_distribution(
                [self._status_label(record.get("status")) for record in records],
                order=["Titolare", "Entrato", "Inutilizzato", "Infortunato", "Squalificato", "Other"],
            ),
        }

    def boxplots_from_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "goals": self._boxplot(
                [self._goal_bucket(record) for record in records],
            ),
            "assists": self._boxplot(
                [self._integer(record.get("assists")) or 0 for record in records],
            ),
            "voto": self._boxplot(
                [self._number(record.get("voto")) for record in records],
            ),
            "fantavoto": self._boxplot(
                [self._number(record.get("fantavoto")) for record in records],
            ),
        }


    def _boxplot(self, values: list[int | float | None]) -> dict[str, Any]:
        clean = sorted(
            float(value)
            for value in values
            if value is not None
        )

        if not clean:
            return {
                "n": 0,
                "min": None,
                "q1": None,
                "median": None,
                "q3": None,
                "max": None,
                "mean": None,
            }

        return {
            "n": len(clean),
            "min": clean[0],
            "q1": self._quantile(clean, 0.25),
            "median": self._quantile(clean, 0.50),
            "q3": self._quantile(clean, 0.75),
            "max": clean[-1],
            "mean": sum(clean) / len(clean),
        }


    @staticmethod
    def _quantile(values: list[float], q: float) -> float:
        if not values:
            return 0.0

        if len(values) == 1:
            return values[0]

        position = (len(values) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        weight = position - lower

        return values[lower] * (1.0 - weight) + values[upper] * weight

    def _goal_bucket(self, record: dict[str, Any]) -> int:
        scored = self._integer(record.get("scoredGoals")) or 0
        own = self._integer(record.get("ownGoals")) or 0

        if own > 0 and scored == 0:
            return -own

        return scored


    def _integer_distribution(
        self,
        values: list[int | None],
        *,
        minimum: int = 0,
    ) -> list[dict[str, Any]]:
        clean = [int(value) for value in values if value is not None]
        if not clean:
            return []

        max_value = max(max(clean), minimum)
        min_value = min(min(clean), minimum)

        counts = {
            value: clean.count(value)
            for value in range(min_value, max_value + 1)
        }

        return self._distribution_payload(counts)


    def _half_step_distribution(
        self,
        values: list[int | float | None],
        *,
        start: float,
        stop: float,
    ) -> list[dict[str, Any]]:
        clean = []

        for value in values:
            if value is None:
                continue

            bucket = round(float(value) * 2) / 2
            bucket = max(start, min(stop, bucket))
            clean.append(bucket)

        if not clean:
            return []

        keys = []
        current = start

        while current <= stop + 1e-9:
            keys.append(round(current, 1))
            current += 0.5

        counts = {
            key: clean.count(key)
            for key in keys
        }

        return self._distribution_payload(counts)


    def _binary_distribution(
        self,
        values: list[bool],
        *,
        yes_label: str,
        no_label: str,
    ) -> list[dict[str, Any]]:
        counts = {
            no_label: values.count(False),
            yes_label: values.count(True),
        }

        return self._distribution_payload(counts)


    def _categorical_distribution(
        self,
        values: list[str],
        *,
        order: list[str],
    ) -> list[dict[str, Any]]:
        counts = {key: 0 for key in order}

        for value in values:
            key = value if value in counts else "Other"
            counts[key] = counts.get(key, 0) + 1

        return self._distribution_payload(counts)


    def _distribution_payload(
        self,
        counts: dict[Any, int],
    ) -> list[dict[str, Any]]:
        total = sum(counts.values())

        if total <= 0:
            return [
                {
                    "value": value,
                    "label": self._format_distribution_label(value),
                    "count": count,
                    "probability": 0.0,
                    "percentage": 0.0,
                }
                for value, count in counts.items()
            ]

        return [
            {
                "value": value,
                "label": self._format_distribution_label(value),
                "count": count,
                "probability": count / total,
                "percentage": round(100.0 * count / total, 2),
            }
            for value, count in counts.items()
        ]


    def _result_label(self, value: Any) -> str:
        number = self._integer(value)

        if number == 1:
            return "Win"

        if number == 0:
            return "Draw"

        if number == -1:
            return "Loss"

        return "Unknown"


    def _status_label(self, value: Any) -> str:
        text = str(value or "").strip()

        if text in {
            "Titolare",
            "Entrato",
            "Inutilizzato",
            "Infortunato",
            "Squalificato",
        }:
            return text

        return "Other"


    def _integer(self, value: Any) -> int | None:
        number = self._number(value)

        if number is None:
            return None

        if isinstance(number, float) and not number.is_integer():
            return None

        return int(number)


    @staticmethod
    def _format_distribution_label(value: Any) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))

        return str(value)

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
