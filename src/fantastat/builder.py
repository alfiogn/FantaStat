from __future__ import annotations

import argparse
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
from pymongo import MongoClient


class Builder:
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

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        if not self.cache_dir.is_dir():
            raise NotADirectoryError(self.cache_dir)

        self.files = self._discover_files()
        self.calendars: dict[int, list[dict[str, Any]]] = {}
        self.quotations: dict[int, list[dict[str, Any]]] = {}
        self.stats: dict[int, dict[str, Any]] = {}

        self.players: dict[str, dict[str, Any]] = {}

        self._load()
    
    def _discover_files(self) -> dict[int, dict[str, Path]]:
        files: dict[int, dict[str, Path]] = defaultdict(dict)

        for path in self.cache_dir.iterdir():
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

        return files
    
    def _load(self) -> None:
        self.calendars = []
        self.quotations = []
        day_to_day_map = {}
        for year in self.years:
            paths = self.files[year]
            calendar = self._load_calendar(paths.get("calendar"))
            quotations = self._load_quotations(paths.get("quotazioni"))
            stats = self._load_stats(paths.get("stats"))

            day = 0
            for e in calendar:
                day_id = len(self.calendars)
                if e['giornata'] > day:
                    self.calendars.append({
                        "_id": str(day_id),
                        "year": year,
                        "giornata": e['giornata'],
                        "matches": []
                    })
                    day = e['giornata']
                self.calendars[-1]['matches'].append(e)
                day_to_day_map[(year, e['giornata'])] = day_id
            self.quotations.append({"_id": str(year), "year": year, "quotations": quotations})
            self.stats[year] = stats

            for player_id, player_stats in stats.items():
                player = self.players.setdefault(
                    player_id,
                    {
                        "_id": player_id.lower().replace(" ", "_"),
                        "name": player_id,
                        "seasons": {}
                    }
                )

                season_records = []

                for record in player_stats.get("records", []):
                    r = dict(record)

                    r["year_id"] = str(year)
                    r["giornata_id"] = str(
                        day_to_day_map[(year, r["giornata"])]
                    )

                    season_records.append(r)

                player["seasons"][str(year)] = {
                    "attrs": dict(player_stats.get("attrs", {})),
                    "records": season_records,
                }

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

    def collections(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "calendars": list(self.calendars),
            "quotations": list(self.quotations),
            "players": list(self.players.values())
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

        # self.create_indexes(database)
        return counts
    
    @property
    def years(self) -> tuple[int, ...]:
        return tuple(sorted(self.files))

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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantastat builddb"
    )

    parser.add_argument(
        "--cache",
        default="cache",
        help="Cache directory",
    )

    parser.add_argument(
        "--uri",
        default="mongodb://localhost:27017",
        help="MongoDB URI",
    )

    parser.add_argument(
        "--database",
        default="fantastat",
        help="Database name",
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop existing collections",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    builder = Builder(args.cache)

    client = MongoClient(args.uri)
    db = client[args.database]

    counts = builder.write_mongodb(
        db,
        replace=args.replace,
    )

    for collection, count in counts.items():
        print(f"{collection}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())