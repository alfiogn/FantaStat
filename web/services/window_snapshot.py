from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any
import re

from repositories.player_repository import PlayerRepository
from repositories.quotation_repository import QuotationRepository
from services.timeline import TimelineService
from services.time_window import TimeWindowService


@dataclass(slots=True)
class WindowSnapshot:
    season: int
    days: int
    created_at: float
    window: dict[str, Any]
    rows: list[dict[str, Any]]
    by_player_id: dict[str, dict[str, Any]]
    timelines: dict[str, dict[str, list[Any]]]
    records: dict[str, list[dict[str, Any]]]


class WindowSnapshotService:
    """In-memory cache for rolling-window player statistics.

    Expensive operation before this service:
        /api/quotations recomputed rolling-window records for every player
        on every request.

    Expensive operation after this service:
        once per (season, days) pair, then reused by dashboard, player page,
        comparison page and derived APIs.

    Cache invalidation is intentionally simple:
        - call clear() after builddb/scrape
        - or wait for ttl_seconds
    """

    def __init__(
        self,
        *,
        quotation_repo: QuotationRepository,
        player_repo: PlayerRepository,
        time_window_service: TimeWindowService,
        timeline_service: TimelineService,
        ttl_seconds: int = 900,
        max_entries: int = 32,
    ):
        self.quotation_repo = quotation_repo
        self.player_repo = player_repo
        self.time_window_service = time_window_service
        self.timeline_service = timeline_service
        self.ttl_seconds = int(ttl_seconds)
        self.max_entries = int(max_entries)
        self._cache: dict[tuple[int, int], WindowSnapshot] = {}
        self._lock = RLock()

    def get_snapshot(self, season: int, days: int) -> WindowSnapshot:
        key = (int(season), int(days))
        now = monotonic()

        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached.created_at <= self.ttl_seconds:
                return cached

        snapshot = self._build_snapshot(int(season), int(days))

        with self._lock:
            self._cache[key] = snapshot
            self._evict_if_needed()

        return snapshot

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def info(self) -> dict[str, Any]:
        now = monotonic()
        with self._lock:
            return {
                "ttl_seconds": self.ttl_seconds,
                "max_entries": self.max_entries,
                "entries": [
                    {
                        "season": season,
                        "days": days,
                        "age_seconds": round(now - snap.created_at, 3),
                        "rows": len(snap.rows),
                    }
                    for (season, days), snap in self._cache.items()
                ],
            }

    def list_rows(
        self,
        season: int,
        days: int,
        *,
        role: str | None = None,
        team: str | None = None,
        search: str | None = None,
        sort: str = "FVM",
        direction: int = -1,
        limit: int = 1000,
    ) -> dict[str, Any]:
        snapshot = self.get_snapshot(season, days)
        rows = list(snapshot.rows)

        if role:
            rows = [row for row in rows if row.get("role") == role]
        if team:
            rows = [row for row in rows if row.get("team") == team]
        if search:
            needle = self._norm(search)
            rows = [row for row in rows if needle in self._norm(row.get("name"))]

        reverse = direction < 0
        rows = sorted(rows, key=lambda row: self._sort_key(row, sort), reverse=reverse)
        rows = rows[: max(1, int(limit))]

        return {
            "season": int(season),
            "days": int(days),
            "window": snapshot.window,
            "cached": True,
            "rows": rows,
        }

    def player_payload(self, player_id: int | str, season: int, days: int) -> dict[str, Any]:
        snapshot = self.get_snapshot(season, days)
        key = self._player_key(player_id)
        row = snapshot.by_player_id.get(key)
        player = self.player_repo.get_player(player_id)

        return {
            "player": player,
            "season": int(season),
            "days": int(days),
            "unit": "matchdays",
            "window": snapshot.window,
            "season_data": self.player_repo.get_player_season(player_id, season),
            "records": snapshot.records.get(key, []),
            "summary": self._summary_from_row(row),
            "cached": True,
        }

    def timeline_payload(self, player_id: int | str, season: int, days: int) -> dict[str, Any]:
        snapshot = self.get_snapshot(season, days)
        key = self._player_key(player_id)
        return {
            "season": int(season),
            "days": int(days),
            "window": snapshot.window,
            "timeline": snapshot.timelines.get(key, self.timeline_service.build([])),
            "cached": True,
        }

    def compare_payload(self, season: int, days: int, ids: list[int | str]) -> dict[str, Any]:
        snapshot = self.get_snapshot(season, days)
        players = []
        for player_id in ids:
            key = self._player_key(player_id)
            row = snapshot.by_player_id.get(key)
            player = self.player_repo.get_player(player_id)
            if not player:
                continue
            players.append(
                {
                    "player_id": player.get("player_id") or player_id,
                    "name": player.get("name"),
                    "team": player.get("team_code") or player.get("team"),
                    "role": player.get("role"),
                    "summary": self._summary_from_row(row),
                    "timeline": snapshot.timelines.get(key, self.timeline_service.build([])),
                }
            )

        return {
            "season": int(season),
            "days": int(days),
            "window": snapshot.window,
            "cached": True,
            "metrics": [
                "window_QI",
                "window_QA",
                "window_quotation_delta",
                "window_FV",
                "window_MV",
                "window_FVM",
                "window_goals",
                "window_assists",
                "window_records",
            ],
            "players": players,
        }

    def _build_snapshot(self, season: int, days: int) -> WindowSnapshot:
        window = self.time_window_service.context(season, days)
        quotation_rows = self.quotation_repo.list_quotations(
            season,
            sort="FVM",
            direction=-1,
            limit=10000,
        )

        rows: list[dict[str, Any]] = []
        by_player_id: dict[str, dict[str, Any]] = {}
        timelines: dict[str, dict[str, list[Any]]] = {}
        records_by_player: dict[str, list[dict[str, Any]]] = {}

        for row in quotation_rows:
            player_id = row.get("player_id")
            if player_id is None:
                enriched = self.time_window_service.enrich_quotation_row(row, season, days)
                rows.append(enriched)
                continue

            key = self._player_key(player_id)
            records = self.time_window_service.window_records(player_id, season, days)
            metrics = self.time_window_service.metrics_from_records(records, row, days)
            enriched = dict(row)
            enriched["window"] = window
            enriched.update(metrics)

            rows.append(enriched)
            by_player_id[key] = enriched
            records_by_player[key] = records
            timelines[key] = self.timeline_service.build(records)

        return WindowSnapshot(
            season=season,
            days=days,
            created_at=monotonic(),
            window=window,
            rows=rows,
            by_player_id=by_player_id,
            timelines=timelines,
            records=records_by_player,
        )

    def _evict_if_needed(self) -> None:
        if len(self._cache) <= self.max_entries:
            return
        oldest_key = min(self._cache, key=lambda key: self._cache[key].created_at)
        self._cache.pop(oldest_key, None)

    @staticmethod
    def _summary_from_row(row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {
                "window_QI": None,
                "window_QA": None,
                "window_quotation_delta": None,
                "window_FV": None,
                "window_MV": None,
                "window_FVM": None,
                "window_goals": 0,
                "window_assists": 0,
                "window_records": 0,
            }
        return {key: value for key, value in row.items() if key.startswith("window_")}

    @staticmethod
    def _player_key(player_id: int | str) -> str:
        try:
            return str(int(player_id))
        except (TypeError, ValueError):
            return str(player_id)

    @staticmethod
    def _norm(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

    @staticmethod
    def _sort_key(row: dict[str, Any], sort: str) -> Any:
        value = row.get(sort)
        if value is None and sort == "FVM":
            value = row.get("window_FVM")
        if value is None:
            return "" if sort == "name" else -10**18
        return value
