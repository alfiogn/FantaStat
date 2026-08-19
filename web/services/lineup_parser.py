from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


class LineupParser:
    """Parse Fantacalcio probable-formation article HTML.

    Extracts only the useful auction data:
    team, coach, module, starting XI, ballottaggi, penalty takers and set-piece takers.
    Ads and article prose are ignored.
    """

    def parse_html(self, html: str, *, season: int | None = None, source: str | None = None) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        teams = []

        for aside in soup.select("aside.text-type-aside"):
            heading = aside.find("h2")
            if not heading:
                continue

            raw = {"team": self._clean(heading.get_text(" ", strip=True))}

            for p in aside.find_all("p"):
                strong = p.find("strong")
                if not strong:
                    continue
                key = self._clean(strong.get_text(" ", strip=True)).strip(":").casefold()
                text = self._clean(p.get_text(" ", strip=True))
                value = text.split(":", 1)[1].strip() if ":" in text else text.replace(strong.get_text(" ", strip=True), "").strip(" :")
                raw[key] = self._clean(value)

            lineup_text = re.sub(
                r"^\(da dx a sx\):\s*",
                "",
                raw.get("probabile formazione", ""),
                flags=re.IGNORECASE,
            )
            groups = self._split_lineup(lineup_text)
            module_text = raw.get("modulo", "")
            module = module_text.split()[0] if module_text else None

            teams.append(
                {
                    "team": raw["team"],
                    "coach": raw.get("allenatore"),
                    "module": module,
                    "module_text": module_text,
                    "lineup_text": lineup_text,
                    "groups": groups,
                    "players": [player for group in groups for player in group],
                    "ballottaggi": raw.get("ballottaggi"),
                    "rigoristi": raw.get("rigoristi"),
                    "calci_da_fermo": raw.get("calci da fermo"),
                }
            )

        return {"season": season, "source": source, "teams": teams}

    def parse_file(self, path: str | Path, *, season: int | None = None) -> dict[str, Any]:
        path = Path(path)
        return self.parse_html(path.read_text(encoding="utf-8"), season=season, source=str(path))

    @staticmethod
    def _split_lineup(text: str) -> list[list[str]]:
        groups = []
        for part in text.split(";"):
            players = [p.strip(" .") for p in part.split(",") if p.strip(" .")]
            if players:
                groups.append(players)
        return groups

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()
