from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
import pandas as pd

class CacheNotFoundError(FileNotFoundError): pass
class PlayerNotFoundError(KeyError): pass

class CacheRepository:
    def __init__(self, cache_dir: str | Path = "cache"):
        self.cache_dir = Path(cache_dir)
        self._lock = RLock()
        self._stats: dict[int, tuple[int, dict[str, pd.DataFrame]]] = {}

    def list_years(self) -> list[int]:
        return sorted(int(p.stem.removeprefix("stats")) for p in self.cache_dir.glob("stats[0-9][0-9][0-9][0-9].json"))

    def load_stats(self, year: int) -> dict[str, pd.DataFrame]:
        path = self.cache_dir / f"stats{year}.json"
        if not path.is_file(): raise CacheNotFoundError(path)
        stamp = path.stat().st_mtime_ns
        with self._lock:
            if year not in self._stats or self._stats[year][0] != stamp:
                raw = json.loads(path.read_text(encoding="utf-8"))
                data = {}
                for name, payload in raw.items():
                    df = pd.DataFrame(payload.get("records", []))
                    df.attrs.update(payload.get("attrs", {}))
                    data[str(name)] = df
                self._stats[year] = (stamp, data)
            return self._stats[year][1]

    def player(self, year: int, name: str) -> tuple[str, pd.DataFrame]:
        data = self.load_stats(year)
        if name in data: return name, data[name]
        wanted = name.casefold().strip()
        found = [(n, d) for n, d in data.items() if n.casefold() == wanted]
        if len(found) != 1: raise PlayerNotFoundError(name)
        return found[0]
