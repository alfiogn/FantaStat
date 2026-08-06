from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Team:
    name: str
    initial_budget: int
    spent: int = 0

    @property
    def remaining_budget(self) -> int:
        return self.initial_budget - self.spent

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Team":
        return cls(
            name=str(data["name"]),
            initial_budget=int(data["initial_budget"]),
            spent=int(data.get("spent", 0)),
        )


@dataclass(slots=True)
class AuctionPlayer:
    name: str
    role: str | None = None
    real_team: str | None = None
    url: str | None = None
    qi: int | float | None = None
    qa: int | float | None = None
    fvm: int | float | None = None
    owner: str | None = None
    price: int | None = None

    @property
    def available(self) -> bool:
        return self.owner is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuctionPlayer":
        return cls(
            name=str(data["name"]),
            role=data.get("role"),
            real_team=data.get("real_team"),
            url=data.get("url"),
            qi=data.get("qi"),
            qa=data.get("qa"),
            fvm=data.get("fvm"),
            owner=data.get("owner"),
            price=data.get("price"),
        )


@dataclass(slots=True)
class AuctionEvent:
    timestamp: str
    action: str
    player: str | None = None
    team: str | None = None
    price: int | None = None
    previous_team: str | None = None
    previous_price: int | None = None
    note: str | None = None

    @classmethod
    def now(
        cls,
        *,
        action: str,
        player: str | None = None,
        team: str | None = None,
        price: int | None = None,
        previous_team: str | None = None,
        previous_price: int | None = None,
        note: str | None = None,
    ) -> "AuctionEvent":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            player=player,
            team=team,
            price=price,
            previous_team=previous_team,
            previous_price=previous_price,
            note=note,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuctionEvent":
        return cls(
            timestamp=str(data["timestamp"]),
            action=str(data["action"]),
            player=data.get("player"),
            team=data.get("team"),
            price=data.get("price"),
            previous_team=data.get("previous_team"),
            previous_price=data.get("previous_price"),
            note=data.get("note"),
        )


@dataclass(slots=True)
class AuctionState:
    year: int
    teams: dict[str, Team]
    players: dict[str, AuctionPlayer]
    events: list[AuctionEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "teams": {name: team.to_dict() for name, team in self.teams.items()},
            "players": {name: player.to_dict() for name, player in self.players.items()},
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuctionState":
        return cls(
            year=int(data["year"]),
            teams={name: Team.from_dict(team) for name, team in data.get("teams", {}).items()},
            players={name: AuctionPlayer.from_dict(player) for name, player in data.get("players", {}).items()},
            events=[AuctionEvent.from_dict(event) for event in data.get("events", [])],
        )
