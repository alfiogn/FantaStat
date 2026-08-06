from __future__ import annotations

import json
from pathlib import Path

from auction_models import AuctionState


class AuctionStore:
    """JSON persistence for one or more auction states."""

    def __init__(self, directory: str | Path = "auctions"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, year: int, name: str = "default") -> Path:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip()) or "default"
        return self.directory / f"auction_{year}_{safe_name}.json"

    def exists(self, year: int, name: str = "default") -> bool:
        return self.path_for(year, name).exists()

    def save(self, state: AuctionState, name: str = "default") -> Path:
        path = self.path_for(state.year, name)
        path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, year: int, name: str = "default") -> AuctionState:
        path = self.path_for(year, name)
        return AuctionState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_auctions(self) -> list[Path]:
        return sorted(self.directory.glob("auction_*.json"))
