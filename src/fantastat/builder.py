from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from typing import Any

from pymongo import MongoClient, ReplaceOne


class Builder:
    """Load Fantastat cache files and build stable MongoDB collections.

    Input folder must contain files named:

    - calendarYYYY.json
    - quotazioniYYYY.csv
    - statsYYYY.json

    Output collections:

    - calendars: one document per season and matchday, with all fixtures inside "matches"
    - calendar_matches: one flattened document per fixture
    - quotations: one document per season, with all quotation rows inside "quotations"
    - quotation_rows: one flattened document per player and season
    - players: one document per player, with all season timelines inside "seasons"
    - teams: one document per team and season

    The nested collections preserve the previous contract.
    The flattened collections make the web application simple and fast.
    """

    FILE_PATTERN = re.compile(
        r"^(calendar|quotazioni|stats)(\d{4})\.(json|csv)$",
        re.IGNORECASE,
    )

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        if not self.cache_dir.is_dir():
            raise NotADirectoryError(self.cache_dir)

        self.files = self._discover_files()

        self.calendars: list[dict[str, Any]] = []
        self.calendar_matches: list[dict[str, Any]] = []
        self.quotations: list[dict[str, Any]] = []
        self.quotation_rows: list[dict[str, Any]] = []
        self.players: dict[str, dict[str, Any]] = {}
        self.teams: dict[str, dict[str, Any]] = {}

        self._load()

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(sorted(self.files))

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
                    f"Duplicate {kind} file for {year}: {files[year][kind]} and {path}"
                )
            files[year][kind] = path
        return dict(files)

    def _load(self) -> None:
        day_to_day_id: dict[tuple[int, int], str] = {}

        for year in self.years:
            paths = self.files[year]
            calendar = self._load_calendar(paths.get("calendar"))
            quotations = self._load_quotations(paths.get("quotazioni"), year=year)
            stats = self._load_stats(paths.get("stats"))

            quotation_by_name = self._quotation_lookup_by_name(quotations)
            quotation_by_player_id = self._quotation_lookup_by_player_id(quotations)

            self._build_calendar_documents(year, calendar, day_to_day_id)
            self._build_quotation_documents(year, quotations)
            self._build_player_documents(
                year,
                stats,
                day_to_day_id,
                quotation_by_name,
                quotation_by_player_id,
            )
            self._build_team_documents(year, calendar, quotations)

    def _build_calendar_documents(
        self,
        year: int,
        calendar: list[dict[str, Any]],
        day_to_day_id: dict[tuple[int, int], str],
    ) -> None:
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for raw in calendar:
            record = self._calendar_record(raw, year)
            giornata = self._integer(record.get("giornata"))
            if giornata is None:
                continue
            grouped[giornata].append(record)

            match_id = self._calendar_match_id(year, giornata, record)
            flat = dict(record)
            flat["_id"] = match_id
            flat["year"] = year
            flat["season"] = year
            flat["matchday"] = giornata
            flat["home_team"] = record.get("team_home")
            flat["away_team"] = record.get("team_away")
            flat["date"] = record.get("match_date")
            flat["played"] = record.get("calendar_match_status") == "FINISHED"
            self.calendar_matches.append(flat)

        for giornata in sorted(grouped):
            doc_id = f"{year}:{giornata}"
            day_to_day_id[(year, giornata)] = doc_id
            self.calendars.append(
                {
                    "_id": doc_id,
                    "year": year,
                    "season": year,
                    "giornata": giornata,
                    "matchday": giornata,
                    "matches": grouped[giornata],
                }
            )

    def _build_quotation_documents(self, year: int, quotations: list[dict[str, Any]]) -> None:
        rows = []
        for row in quotations:
            q = self._quotation_row(row, year)
            rows.append(q)
            self.quotation_rows.append(q)

        self.quotations.append(
            {
                "_id": str(year),
                "year": year,
                "season": year,
                "quotations": rows,
            }
        )

    def _build_player_documents(
        self,
        year: int,
        stats: Mapping[str, Any],
        day_to_day_id: dict[tuple[int, int], str],
        quotation_by_name: Mapping[str, dict[str, Any]],
        quotation_by_player_id: Mapping[int, dict[str, Any]],
    ) -> None:
        for stats_key, payload in stats.items():
            if not isinstance(payload, Mapping):
                continue

            attrs = dict(payload.get("attrs", {})) if isinstance(payload.get("attrs"), Mapping) else {}
            bridge = attrs.get("bridge", {}) if isinstance(attrs.get("bridge"), Mapping) else {}

            player_id = self._integer(bridge.get("playerId"))
            player_name = str(bridge.get("playerName") or stats_key)

            quotation = None
            if player_id is not None:
                quotation = quotation_by_player_id.get(player_id)
            if quotation is None:
                quotation = quotation_by_name.get(self._key(player_name))
            if quotation is None:
                quotation = quotation_by_name.get(self._key(stats_key))

            if player_id is None and quotation is not None:
                player_id = self._integer(quotation.get("player_id"))

            player_doc_id = str(player_id) if player_id is not None else self._slug(player_name)

            player = self.players.setdefault(
                player_doc_id,
                {
                    "_id": player_doc_id,
                    "player_id": player_id,
                    "name": player_name,
                    "role": None,
                    "team": None,
                    "seasons": {},
                    "source_keys": [],
                },
            )

            if stats_key not in player["source_keys"]:
                player["source_keys"].append(stats_key)

            self._merge_identity(player, attrs, bridge, quotation)

            records = []
            for raw in payload.get("records", []):
                if not isinstance(raw, Mapping):
                    continue
                record = self._player_record(raw, year, day_to_day_id)
                records.append(record)

            summary = self._summary_from_records(records, quotation)

            player["seasons"][str(year)] = {
                "year": year,
                "season": year,
                "attrs": attrs,
                "records": records,
                "summary": summary,
                "quotation": quotation,
            }

    def _build_team_documents(
        self,
        year: int,
        calendar: list[dict[str, Any]],
        quotations: list[dict[str, Any]],
    ) -> None:
        known: dict[str, dict[str, Any]] = {}

        for match in calendar:
            for field in ("team_home", "team_away"):
                name = match.get(field)
                if name:
                    key = self._key(name)
                    known[key] = {
                        "team_code": str(name),
                        "team_name": str(name),
                        "season": year,
                        "year": year,
                    }

        for row in quotations:
            code = row.get("squadra") or row.get("team")
            slug = row.get("team_slug")
            if code:
                key = self._key(code)
                known[key] = {
                    "team_code": str(code),
                    "team_name": str(slug or code),
                    "season": year,
                    "year": year,
                }

        for key, team in known.items():
            doc_id = f"{year}:{key}"
            self.teams[doc_id] = {"_id": doc_id, **team}

    def _load_calendar(self, path: Path | None) -> list[dict[str, Any]]:
        if path is None:
            return []
        data = self._read_json(path)
        if not isinstance(data, Mapping):
            raise TypeError(f"{path}: expected a JSON object")
        records = data.get("records", [])
        if not isinstance(records, list):
            raise TypeError(f"{path}: 'records' must be a list")
        return [dict(item) for item in records if isinstance(item, Mapping)]

    def _load_quotations(self, path: Path | None, *, year: int) -> list[dict[str, Any]]:
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
                row["name"] = row.get("nome")
                row["team"] = row.get("squadra")
                row["team_slug"] = row.get("team_slug")
                row["role"] = row.get("ruolo")
                row["season"] = year
                row["year"] = year

                row["QI"] = self._number(row.get("QI"))
                row["QA"] = self._number(row.get("QA"))
                row["FVM"] = self._number(row.get("FVM"))
                row["quotation"] = row.get("QA")
                row["initial_quotation"] = row.get("QI")
                row["current_quotation"] = row.get("QA")
                row["quotation_delta"] = self._difference(row.get("QA"), row.get("QI"))
                row["quotation_growth_pct"] = self._growth_percentage(row.get("QA"), row.get("QI"))

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

    def _calendar_record(self, raw: Mapping[str, Any], year: int) -> dict[str, Any]:
        record = dict(raw)
        giornata = self._integer(record.get("giornata"))
        record["year"] = year
        record["season"] = year
        record["matchday"] = giornata
        record["giornata"] = giornata
        record["home_team"] = record.get("team_home")
        record["away_team"] = record.get("team_away")
        record["date"] = record.get("match_date")
        record["played"] = record.get("calendar_match_status") == "FINISHED"
        return record

    def _quotation_row(self, row: Mapping[str, Any], year: int) -> dict[str, Any]:
        player_id = self._integer(row.get("player_id"))
        name = row.get("name") or row.get("nome")
        team = row.get("team") or row.get("squadra")
        role = row.get("role") or row.get("ruolo")

        doc = dict(row)
        doc["_id"] = f"{year}:{player_id}" if player_id is not None else f"{year}:{self._slug(name)}"
        doc["player_id"] = player_id
        doc["name"] = name
        doc["team"] = team
        doc["role"] = role
        doc["season"] = year
        doc["year"] = year
        doc["QI"] = self._number(doc.get("QI"))
        doc["QA"] = self._number(doc.get("QA"))
        doc["FVM"] = self._number(doc.get("FVM"))
        doc["quotation"] = doc.get("QA")
        doc["initial_quotation"] = doc.get("QI")
        doc["current_quotation"] = doc.get("QA")
        doc["quotation_delta"] = self._difference(doc.get("QA"), doc.get("QI"))
        doc["quotation_growth_pct"] = self._growth_percentage(doc.get("QA"), doc.get("QI"))
        return doc

    def _player_record(
        self,
        raw: Mapping[str, Any],
        year: int,
        day_to_day_id: Mapping[tuple[int, int], str],
    ) -> dict[str, Any]:
        record = dict(raw)
        giornata = self._integer(record.get("giornata"))
        record["year"] = year
        record["season"] = year
        record["matchday"] = giornata
        record["giornata"] = giornata
        record["year_id"] = str(year)
        record["giornata_id"] = day_to_day_id.get((year, giornata)) if giornata is not None else None
        record["played"] = bool(record.get("played"))
        return record

    def _summary_from_records(
        self,
        records: list[dict[str, Any]],
        quotation: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        valid = [r for r in records if r]
        voted = [r for r in valid if self._number(r.get("fantavoto")) is not None]
        starters = [r for r in valid if r.get("status") == "Titolare"]
        sub_ins = [r for r in valid if r.get("status") == "Entrato"]

        def avg(field: str) -> float | None:
            values = [self._number(r.get(field)) for r in valid]
            values = [v for v in values if v is not None]
            return round(mean(values), 3) if values else None

        def total(field: str) -> int | float:
            values = [self._number(r.get(field)) for r in valid]
            return sum(v for v in values if v is not None)

        last_giornata = max(
            [g for g in (self._integer(r.get("giornata")) for r in valid) if g is not None],
            default=None,
        )

        summary = {
            "records": len(valid),
            "appearances": len(voted),
            "starts": len(starters),
            "sub_ins": len(sub_ins),
            "last_matchday": last_giornata,
            "avg_vote": avg("voto"),
            "avg_fantavote": avg("fantavoto"),
            "goals": total("scoredGoals"),
            "assists": total("assists"),
            "yellow_cards": total("yellowCards"),
            "red_cards": total("redCards"),
            "own_goals": total("ownGoals"),
            "current_price": None,
            "initial_price": None,
            "fvm": None,
        }

        prices = [self._number(r.get("quotazione_classic")) for r in valid]
        prices = [p for p in prices if p is not None]
        if prices:
            summary["current_price"] = prices[-1]
            summary["max_price"] = max(prices)
            summary["min_price"] = min(prices)

        if quotation is not None:
            summary["current_price"] = self._number(quotation.get("QA")) or summary["current_price"]
            summary["initial_price"] = self._number(quotation.get("QI"))
            summary["fvm"] = self._number(quotation.get("FVM"))
            summary["quotation_delta"] = self._number(quotation.get("quotation_delta"))
            summary["quotation_growth_pct"] = self._number(quotation.get("quotation_growth_pct"))

        return summary

    def _merge_identity(
        self,
        player: dict[str, Any],
        attrs: Mapping[str, Any],
        bridge: Mapping[str, Any],
        quotation: Mapping[str, Any] | None,
    ) -> None:
        player["player_id"] = player.get("player_id") or self._integer(bridge.get("playerId"))
        player["name"] = bridge.get("playerName") or player.get("name")
        player["role"] = bridge.get("playerPosition") or player.get("role")
        player["team"] = bridge.get("teamName") or player.get("team")

        if quotation is not None:
            player["player_id"] = player.get("player_id") or self._integer(quotation.get("player_id"))
            player["name"] = player.get("name") or quotation.get("name")
            player["role"] = player.get("role") or quotation.get("role")
            player["team"] = player.get("team") or quotation.get("team")
            player["team_code"] = quotation.get("team")
            player["team_slug"] = quotation.get("team_slug")

        for key in ("age", "birth_date", "height", "height_cm", "weight", "nationality"):
            value = attrs.get(key)
            if value is not None and player.get(key) is None:
                player[key] = value

    def _quotation_lookup_by_name(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        lookup = {}
        for row in rows:
            name = row.get("name") or row.get("nome")
            if name:
                lookup[self._key(name)] = row
        return lookup

    def _quotation_lookup_by_player_id(self, rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        lookup = {}
        for row in rows:
            player_id = self._integer(row.get("player_id"))
            if player_id is not None:
                lookup[player_id] = row
        return lookup

    def collections(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "calendars": list(self.calendars),
            "calendar_matches": list(self.calendar_matches),
            "quotations": list(self.quotations),
            "quotation_rows": list(self.quotation_rows),
            "players": list(self.players.values()),
            "teams": list(self.teams.values()),
        }

    def write_mongodb(self, database: Any, *, replace: bool = False) -> dict[str, int]:
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
        database.players.create_index("player_id", sparse=True)
        database.players.create_index("name")
        database.players.create_index("team")
        database.players.create_index("role")

        database.quotations.create_index("year", unique=True)
        database.quotations.create_index("season", unique=True)

        database.quotation_rows.create_index([("player_id", 1), ("season", 1)], unique=False, sparse=True)
        database.quotation_rows.create_index([("season", 1), ("team", 1)])
        database.quotation_rows.create_index([("season", 1), ("role", 1)])
        database.quotation_rows.create_index([("season", 1), ("FVM", -1)])
        database.quotation_rows.create_index([("season", 1), ("QA", -1)])
        database.quotation_rows.create_index("name")

        database.calendars.create_index([("season", 1), ("matchday", 1)], unique=True)
        database.calendar_matches.create_index([("season", 1), ("matchday", 1)])
        database.calendar_matches.create_index([("season", 1), ("home_team", 1)])
        database.calendar_matches.create_index([("season", 1), ("away_team", 1)])

        database.teams.create_index([("season", 1), ("team_code", 1)], unique=False)

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
    def _growth_percentage(cls, current: Any, initial: Any) -> float | None:
        current_number = cls._number(current)
        initial_number = cls._number(initial)
        if current_number is None or initial_number in (None, 0):
            return None
        return 100.0 * (current_number - initial_number) / initial_number

    @staticmethod
    def _player_id_from_url(value: Any) -> int | None:
        if not isinstance(value, str):
            return None
        text = value.strip().rstrip("/")
        match = re.search(r"/(\d+)(?:/\d{4}-\d{2})?$", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _calendar_match_id(year: int, giornata: int, record: Mapping[str, Any]) -> str:
        raw = record.get("raw_serie_a_match")
        if isinstance(raw, Mapping):
            match_id = raw.get("matchId") or raw.get("providerId")
            if match_id:
                return f"{year}:{match_id}"
        home = str(record.get("team_home") or "home")
        away = str(record.get("team_away") or "away")
        return f"{year}:{giornata}:{Builder._slug(home)}:{Builder._slug(away)}"

    @staticmethod
    def _slug(value: Any) -> str:
        text = str(value or "unknown").casefold()
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        return text or "unknown"

    @staticmethod
    def _key(value: Any) -> str:
        text = str(value or "").casefold()
        text = re.sub(r"\s+", " ", text).strip()
        return text


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fantastat builddb")
    parser.add_argument("--cache", default="cache", help="Cache directory")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--database", default="fantastat", help="Database name")
    parser.add_argument("--replace", action="store_true", help="Replace existing documents")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    builder = Builder(args.cache)
    client = MongoClient(args.uri)
    db = client[args.database]

    counts = builder.write_mongodb(db, replace=args.replace)
    for collection, count in counts.items():
        print(f"{collection}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
