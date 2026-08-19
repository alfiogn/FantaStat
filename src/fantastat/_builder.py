from __future__ import annotations

import csv
import json
import math
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any


class Builder:
    """Load Fantastat cache files and build MongoDB-compatible collections."""

    FILE_PATTERN = re.compile(
        r"^(calendar|quotazioni|stats)(\d{4})\.(json|csv)$",
        re.IGNORECASE,
    )

    DEFAULT_METRICS = (
        "played",
        "win",
        "voto",
        "fantavoto",
        "bonus_graph",
        "malus_graph",
        "assists",
        "scoredGoals",
        "yellowCards",
        "redCards",
        "ownGoals",
        "savedPenalties",
        "missedPenalties",
        "sub_in_minute",
        "sub_out_minute",
        "quotazione_classic",
        "quotazione_mantra",
        "QI",
        "QA",
        "FVM",
        "quotation_delta",
        "quotation_growth_pct",
    )

    GROUPS = {
        "team": ("team",),
        "team_role": ("team", "role"),
        "team-role": ("team", "role"),
        "player": ("player_id", "player_name"),
        "role": ("role",),
        "age": ("age",),
        "height": ("height_cm",),
    }

    def __init__(self, folder: str | Path):
        self.folder = Path(folder).expanduser().resolve()
        if not self.folder.is_dir():
            raise NotADirectoryError(self.folder)

        self.files = self._discover_files()
        self.calendars: dict[int, list[dict[str, Any]]] = {}
        self.quotations: dict[int, list[dict[str, Any]]] = {}
        self.stats: dict[int, dict[str, Any]] = {}

        self.players: dict[str, dict[str, Any]] = {}
        self.player_seasons: list[dict[str, Any]] = []
        self.fixtures: list[dict[str, Any]] = []
        self.observations: list[dict[str, Any]] = []
        self.records_by_year: dict[int, list[dict[str, Any]]] = {}

        self._observation_dates: list[datetime] = []
        self._load()

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(sorted(self.files))

    @property
    def complete_years(self) -> tuple[int, ...]:
        required = {"calendar", "quotazioni", "stats"}
        return tuple(
            year
            for year in self.years
            if required.issubset(self.files[year])
        )

    @property
    def incomplete_years(self) -> dict[int, tuple[str, ...]]:
        required = {"calendar", "quotazioni", "stats"}
        return {
            year: tuple(sorted(required - set(self.files[year])))
            for year in self.years
            if not required.issubset(self.files[year])
        }

    @property
    def records(self) -> list[dict[str, Any]]:
        return self.observations

    def _discover_files(self) -> dict[int, dict[str, Path]]:
        files: dict[int, dict[str, Path]] = defaultdict(dict)

        for path in self.folder.iterdir():
            if not path.is_file():
                continue

            match = self.FILE_PATTERN.fullmatch(path.name)
            if not match:
                continue

            kind = match.group(1).lower()
            year = int(match.group(2))

            if kind in files[year]:
                raise ValueError(
                    f"Duplicate {kind} file for {year}: "
                    f"{files[year][kind]} and {path}"
                )

            files[year][kind] = path

        if not files:
            raise FileNotFoundError(
                "No calendarYYYY.json, quotazioniYYYY.csv or "
                f"statsYYYY.json files found in {self.folder}"
            )

        return {
            year: dict(sorted(year_files.items()))
            for year, year_files in sorted(files.items())
        }

    def _load(self) -> None:
        for year in self.years:
            paths = self.files[year]
            calendar = self._load_calendar(paths.get("calendar"))
            quotations = self._load_quotations(paths.get("quotazioni"))
            stats = self._load_stats(paths.get("stats"))

            self.calendars[year] = calendar
            self.quotations[year] = quotations
            self.stats[year] = stats

            self._build_fixtures(year, calendar)
            self._build_year(year, quotations, stats)

        self.fixtures.sort(key=self._chronological_key)
        self.observations.sort(key=self._chronological_key)
        self.player_seasons.sort(
            key=lambda item: (
                item.get("year", 9999),
                self._sort_value(item.get("player_id")),
                str(item.get("player_name") or ""),
            )
        )

        self.records_by_year = {
            year: [
                record
                for record in self.observations
                if record.get("year") == year
            ]
            for year in self.years
        }

        self._observation_dates = [
            record["match_date"]
            for record in self.observations
            if isinstance(record.get("match_date"), datetime)
        ]

    def _load_calendar(
        self,
        path: Path | None,
    ) -> list[dict[str, Any]]:
        if path is None:
            return []

        data = self._read_json(path)
        if not isinstance(data, Mapping):
            raise TypeError(f"{path}: expected a JSON object")

        records = data.get("records", [])
        if not isinstance(records, list):
            raise TypeError(f"{path}: 'records' must be a list")

        return [dict(item) for item in records if isinstance(item, Mapping)]

    def _load_quotations(
        self,
        path: Path | None,
    ) -> list[dict[str, Any]]:
        if path is None:
            return []

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                row = {
                    str(key).strip(): self._normalise_scalar(value)
                    for key, value in raw.items()
                    if key is not None
                }
                row["player_id"] = self._player_id_from_url(row.get("url"))
                row["QI"] = self._number(row.get("QI"))
                row["QA"] = self._number(row.get("QA"))
                row["FVM"] = self._number(row.get("FVM"))
                row["quotation_delta"] = self._difference(
                    row.get("QA"),
                    row.get("QI"),
                )
                row["quotation_growth_pct"] = self._growth_percentage(
                    row.get("QA"),
                    row.get("QI"),
                )
                rows.append(row)

        return rows

    def _load_stats(self, path: Path | None) -> dict[str, Any]:
        if path is None:
            return {}

        data = self._read_json(path)
        if not isinstance(data, Mapping):
            raise TypeError(f"{path}: expected a JSON object")

        return {
            str(name): dict(content)
            for name, content in data.items()
            if isinstance(content, Mapping)
        }

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _build_fixtures(
        self,
        year: int,
        calendar: Sequence[Mapping[str, Any]],
    ) -> None:
        for index, source in enumerate(calendar):
            fixture = self._mongo_value(dict(source))
            fixture["year"] = year
            fixture["match_date"] = self._datetime(fixture.get("match_date"))
            fixture["_id"] = self._fixture_id(year, fixture, index)
            self.fixtures.append(fixture)

    def _build_year(
        self,
        year: int,
        quotations: Sequence[Mapping[str, Any]],
        stats: Mapping[str, Any],
    ) -> None:
        quotes_by_id = {
            quote["player_id"]: dict(quote)
            for quote in quotations
            if quote.get("player_id") is not None
        }
        quotes_by_name = {
            self._normalise_name(quote.get("nome")): dict(quote)
            for quote in quotations
            if quote.get("nome")
        }

        found_season_keys: set[tuple[int, Any]] = set()

        for source_name, raw_content in stats.items():
            if not isinstance(raw_content, Mapping):
                continue

            content = dict(raw_content)
            attrs = self._as_dict(content.get("attrs"))
            bridge = self._as_dict(attrs.get("bridge"))
            player_data = self._as_dict(attrs.get("player_data"))

            player_id = self._integer(
                bridge.get("playerId")
                or bridge.get("player_id")
                or attrs.get("playerId")
                or attrs.get("player_id")
            )
            player_name = str(
                bridge.get("playerName")
                or bridge.get("player_name")
                or source_name
            )

            quote = quotes_by_id.get(player_id)
            if quote is None:
                quote = quotes_by_name.get(
                    self._normalise_name(player_name),
                    {},
                )

            player_id = player_id or self._integer(quote.get("player_id"))
            player_key = self._player_key(player_id, player_name)
            birth_date = self._date(player_data.get("Nato il"))
            height_cm = self._height(player_data.get("Altezza"))
            foot = self._clean_text(player_data.get("Piede"))
            nationality = self._clean_text(
                player_data.get("Nazionalità")
                or player_data.get("Nazionalita")
            )

            self._merge_player(
                {
                    "_id": player_key,
                    "player_id": player_id,
                    "player_name": player_name,
                    "birth_date": birth_date,
                    "height_cm": height_cm,
                    "foot": foot,
                    "nationality": nationality,
                }
            )

            role = self._clean_text(
                bridge.get("playerPosition")
                or bridge.get("player_position")
                or quote.get("ruolo")
            )
            team = self._clean_text(
                bridge.get("teamName")
                or bridge.get("team_name")
                or quote.get("squadra")
            )

            season = self._season_document(
                year=year,
                player_key=player_key,
                player_id=player_id,
                player_name=player_name,
                team=team,
                role=role,
                quote=quote,
            )
            self.player_seasons.append(season)
            found_season_keys.add((year, player_id or player_key))

            source_records = content.get("records", [])
            if not isinstance(source_records, list):
                raise TypeError(
                    f"stats{year}: records for {player_name!r} must be a list"
                )

            for index, source_record in enumerate(source_records):
                if not isinstance(source_record, Mapping):
                    continue

                observation = self._observation_document(
                    year=year,
                    player_key=player_key,
                    player_id=player_id,
                    player_name=player_name,
                    team=team,
                    role=role,
                    birth_date=birth_date,
                    height_cm=height_cm,
                    foot=foot,
                    nationality=nationality,
                    quote=quote,
                    source=source_record,
                    index=index,
                )
                self.observations.append(observation)

        self._add_quoted_players_without_stats(
            year,
            quotations,
            found_season_keys,
        )

    def _merge_player(self, incoming: dict[str, Any]) -> None:
        key = incoming["_id"]
        current = self.players.get(key)
        if current is None:
            self.players[key] = incoming
            return

        for field, value in incoming.items():
            if current.get(field) is None and value is not None:
                current[field] = value

    def _season_document(
        self,
        *,
        year: int,
        player_key: str,
        player_id: int | None,
        player_name: str,
        team: str | None,
        role: str | None,
        quote: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "_id": f"{year}:{player_key}",
            "year": year,
            "player_id": player_id,
            "player_name": player_name,
            "team": team,
            "role": role,
            "QI": self._number(quote.get("QI")),
            "QA": self._number(quote.get("QA")),
            "FVM": self._number(quote.get("FVM")),
            "quotation_delta": self._number(quote.get("quotation_delta")),
            "quotation_growth_pct": self._number(
                quote.get("quotation_growth_pct")
            ),
        }

    def _observation_document(
        self,
        *,
        year: int,
        player_key: str,
        player_id: int | None,
        player_name: str,
        team: str | None,
        role: str | None,
        birth_date: date | None,
        height_cm: int | float | None,
        foot: str | None,
        nationality: str | None,
        quote: Mapping[str, Any],
        source: Mapping[str, Any],
        index: int,
    ) -> dict[str, Any]:
        record = self._mongo_value(dict(source))
        match_date = self._datetime(record.get("match_date"))
        event_counts = record.get("event_counts")

        if isinstance(event_counts, Mapping):
            for name, value in event_counts.items():
                record.setdefault(str(name), self._number(value))

        played = record.get("played")
        if isinstance(played, bool):
            played = int(played)
        else:
            played = self._integer(played)

        record.update(
            {
                "year": year,
                "player_id": player_id,
                "player_name": player_name,
                "team": self._clean_text(record.get("active_team")) or team,
                "role": role,
                "birth_date": birth_date,
                "age": self._age(birth_date, match_date),
                "height_cm": height_cm,
                "foot": foot,
                "nationality": nationality,
                "match_date": match_date,
                "played": played,
                "QI": self._number(quote.get("QI")),
                "QA": self._number(quote.get("QA")),
                "FVM": self._number(quote.get("FVM")),
                "quotation_delta": self._number(quote.get("quotation_delta")),
                "quotation_growth_pct": self._number(
                    quote.get("quotation_growth_pct")
                ),
            }
        )
        record["_id"] = self._observation_id(
            year,
            player_key,
            record,
            index,
        )
        return record

    def _add_quoted_players_without_stats(
        self,
        year: int,
        quotations: Sequence[Mapping[str, Any]],
        found: set[tuple[int, Any]],
    ) -> None:
        for quote in quotations:
            player_id = self._integer(quote.get("player_id"))
            player_name = str(quote.get("nome") or "").strip()
            player_key = self._player_key(player_id, player_name)
            season_key = (year, player_id or player_key)

            if season_key in found:
                continue

            self._merge_player(
                {
                    "_id": player_key,
                    "player_id": player_id,
                    "player_name": player_name,
                    "birth_date": None,
                    "height_cm": None,
                    "foot": None,
                    "nationality": None,
                }
            )
            self.player_seasons.append(
                self._season_document(
                    year=year,
                    player_key=player_key,
                    player_id=player_id,
                    player_name=player_name,
                    team=self._clean_text(quote.get("squadra")),
                    role=self._clean_text(quote.get("ruolo")),
                    quote=quote,
                )
            )

    def year(self, year: int) -> list[dict[str, Any]]:
        return list(self.records_by_year.get(year, []))

    def last_days(
        self,
        days: int,
        *,
        reference: datetime | str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        if days < 1:
            raise ValueError("days must be at least 1")

        dated = [
            record
            for record in self.observations
            if isinstance(record.get("match_date"), datetime)
            and (year is None or record.get("year") == year)
        ]
        if not dated:
            return []

        dates = [record["match_date"] for record in dated]
        end = self._datetime(reference) if reference is not None else dates[-1]
        if end is None:
            raise ValueError(f"Invalid reference datetime: {reference!r}")

        start = end - timedelta(days=days)
        left = bisect_left(dates, start)
        right = bisect_right(dates, end)
        return dated[left:right]

    def query(
        self,
        *,
        year: int | None = None,
        days: int | None = None,
        reference: datetime | str | None = None,
        played_only: bool = False,
        team: str | None = None,
        role: str | None = None,
        player_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if days is not None:
            source = self.last_days(days, reference=reference, year=year)
        elif year is not None:
            source = self.year(year)
        else:
            source = list(self.observations)

        return [
            record
            for record in source
            if (not played_only or record.get("played") == 1)
            and (team is None or record.get("team") == team)
            and (role is None or record.get("role") == role)
            and (player_id is None or record.get("player_id") == player_id)
        ]

    def aggregate(
        self,
        by: str | Sequence[str],
        *,
        records: Iterable[Mapping[str, Any]] | None = None,
        metrics: Sequence[str] | None = None,
        min_records: int = 1,
    ) -> list[dict[str, Any]]:
        if min_records < 1:
            raise ValueError("min_records must be at least 1")

        if isinstance(by, str):
            fields = self.GROUPS.get(by)
            if fields is None:
                raise ValueError(
                    f"Unknown aggregation {by!r}. "
                    f"Available: {', '.join(self.GROUPS)}"
                )
        else:
            fields = tuple(by)
            if not fields:
                raise ValueError("At least one grouping field is required")

        selected_metrics = tuple(metrics or self.DEFAULT_METRICS)
        source = self.observations if records is None else records
        groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)

        for record in source:
            key = tuple(record.get(field) for field in fields)
            if any(value is None for value in key):
                continue
            groups[key].append(record)

        output: list[dict[str, Any]] = []
        for key, group in groups.items():
            if len(group) < min_records:
                continue

            item = dict(zip(fields, key))
            item["record_count"] = len(group)
            item["appearance_count"] = sum(
                record.get("played") == 1 for record in group
            )

            for metric in selected_metrics:
                values = [
                    value
                    for record in group
                    if (value := self._number(record.get(metric))) is not None
                ]
                if not values:
                    continue

                item[metric] = {
                    "count": len(values),
                    "sum": sum(values),
                    "mean": mean(values),
                    "min": min(values),
                    "max": max(values),
                }

            output.append(self._mongo_value(item))

        output.sort(
            key=lambda item: tuple(
                self._sort_value(item.get(field)) for field in fields
            )
        )
        return output

    def aggregations(
        self,
        *,
        records: Iterable[Mapping[str, Any]] | None = None,
        metrics: Sequence[str] | None = None,
        min_records: int = 1,
    ) -> dict[str, list[dict[str, Any]]]:
        source = list(records) if records is not None else self.observations
        return {
            name: self.aggregate(
                name,
                records=source,
                metrics=metrics,
                min_records=min_records,
            )
            for name in ("team", "team_role", "player", "role", "age", "height")
        }

    def collections(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "players": list(self.players.values()),
            "player_seasons": list(self.player_seasons),
            "fixtures": list(self.fixtures),
            "observations": list(self.observations),
        }

    def write_mongodb(
        self,
        database: Any,
        *,
        replace: bool = False,
    ) -> dict[str, int]:
        try:
            from pymongo import ReplaceOne
        except ImportError as error:
            raise RuntimeError(
                "pymongo is required by write_mongodb()"
            ) from error

        counts: dict[str, int] = {}
        for name, documents in self.collections().items():
            collection = database[name]
            if replace:
                collection.delete_many({})

            operations = [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in documents
            ]
            if operations:
                collection.bulk_write(operations, ordered=False)
            counts[name] = len(documents)

        self.create_indexes(database)
        return counts

    @staticmethod
    def create_indexes(database: Any) -> None:
        database.players.create_index("player_id")
        database.players.create_index("birth_date")
        database.players.create_index("height_cm")

        database.player_seasons.create_index(
            [("year", 1), ("player_id", 1)],
            unique=True,
        )
        database.player_seasons.create_index(
            [("year", 1), ("team", 1), ("role", 1)]
        )

        database.fixtures.create_index(
            [("year", 1), ("giornata", 1)]
        )
        database.fixtures.create_index("match_date")

        database.observations.create_index(
            [("year", 1), ("player_id", 1), ("giornata", 1)]
        )
        database.observations.create_index("match_date")
        database.observations.create_index(
            [("year", 1), ("team", 1), ("role", 1)]
        )
        database.observations.create_index(
            [("year", 1), ("age", 1)]
        )
        database.observations.create_index(
            [("year", 1), ("height_cm", 1)]
        )

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None

    @classmethod
    def _normalise_name(cls, value: Any) -> str:
        return (cls._clean_text(value) or "").casefold()

    @classmethod
    def _normalise_scalar(cls, value: Any) -> Any:
        if value is None or not isinstance(value, str):
            return value

        text = value.strip()
        if not text:
            return None

        number = cls._number(text)
        return number if number is not None else text

    @staticmethod
    def _number(value: Any) -> int | float | None:
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return value if math.isfinite(value) else None

        if not isinstance(value, str):
            return None

        text = value.strip().replace(" ", "").replace(",", ".")
        if not text:
            return None

        try:
            number = float(text)
        except ValueError:
            return None

        if not math.isfinite(number):
            return None
        return int(number) if number.is_integer() else number

    @classmethod
    def _integer(cls, value: Any) -> int | None:
        number = cls._number(value)
        if number is None:
            return None
        if isinstance(number, float) and not number.is_integer():
            return None
        return int(number)

    @classmethod
    def _difference(cls, current: Any, initial: Any) -> int | float | None:
        current_number = cls._number(current)
        initial_number = cls._number(initial)
        if current_number is None or initial_number is None:
            return None
        return current_number - initial_number

    @classmethod
    def _growth_percentage(
        cls,
        current: Any,
        initial: Any,
    ) -> float | None:
        current_number = cls._number(current)
        initial_number = cls._number(initial)
        if current_number is None or initial_number in (None, 0):
            return None
        return 100.0 * (current_number - initial_number) / initial_number

    @staticmethod
    def _player_id_from_url(value: Any) -> int | None:
        if not isinstance(value, str):
            return None

        match = re.search(r"/(\d+)/\d{4}-\d{2}/?$", value.strip())
        return int(match.group(1)) if match else None

    @classmethod
    def _player_key(cls, player_id: Any, player_name: Any) -> str:
        identifier = cls._integer(player_id)
        if identifier is not None:
            return str(identifier)

        name = cls._normalise_name(player_name)
        if not name:
            raise ValueError("Player has neither player_id nor player_name")
        return f"name:{name}"

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            return None

        text = value.strip()
        for pattern in (
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d.%m.%Y",
        ):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, datetime.min.time())
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
        else:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _height(cls, value: Any) -> int | float | None:
        if value is None:
            return None

        match = re.search(r"\d+(?:[.,]\d+)?", str(value))
        if not match:
            return None

        height = float(match.group().replace(",", "."))
        if 1.0 <= height <= 3.0:
            height *= 100

        if not 100 <= height <= 250:
            return None

        rounded = round(height, 1)
        return int(rounded) if rounded.is_integer() else rounded

    @staticmethod
    def _age(
        birth_date: date | None,
        reference: datetime | None,
    ) -> int | None:
        if birth_date is None or reference is None:
            return None

        current = reference.date()
        age = (
            current.year
            - birth_date.year
            - (
                (current.month, current.day)
                < (birth_date.month, birth_date.day)
            )
        )
        return age if 0 <= age <= 100 else None

    @classmethod
    def _fixture_id(
        cls,
        year: int,
        fixture: Mapping[str, Any],
        index: int,
    ) -> str:
        raw = fixture.get("raw_serie_a_match")
        if isinstance(raw, Mapping):
            provider_id = raw.get("matchId") or raw.get("providerId")
            if provider_id is not None:
                return f"{year}:{provider_id}"

        return ":".join(
            str(value)
            for value in (
                year,
                fixture.get("giornata", index),
                fixture.get("team_home", "unknown"),
                fixture.get("team_away", "unknown"),
            )
        )

    @staticmethod
    def _observation_id(
        year: int,
        player_key: str,
        record: Mapping[str, Any],
        index: int,
    ) -> str:
        return ":".join(
            str(value)
            for value in (
                year,
                player_key,
                record.get("giornata", index),
                record.get("record_type", "unknown"),
            )
        )

    @classmethod
    def _chronological_key(
        cls,
        record: Mapping[str, Any],
    ) -> tuple[Any, ...]:
        return (
            cls._datetime(record.get("match_date"))
            or datetime.max.replace(tzinfo=timezone.utc),
            record.get("year", 9999),
            record.get("giornata", 9999),
            cls._sort_value(record.get("player_id")),
            str(record.get("player_name") or ""),
        )

    @staticmethod
    def _sort_value(value: Any) -> tuple[int, str]:
        return (value is None, str(value) if value is not None else "")

    @classmethod
    def _mongo_value(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return cls._datetime(value)
        if isinstance(value, date):
            return datetime.combine(
                value,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, str):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Mapping):
            return {
                str(key): cls._mongo_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._mongo_value(item) for item in value]
        return str(value)
