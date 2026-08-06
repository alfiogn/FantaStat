from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

import pandas as pd

from auction_models import AuctionEvent, AuctionPlayer, AuctionState, Team
from auction_store import AuctionStore


class AuctionError(ValueError):
    pass


class AuctionService:
    """Business logic for a Fantacalcio auction.

    The state is explicit and serialisable. The UI should call this service,
    never mutate teams or players directly.
    """

    def __init__(self, state: AuctionState, store: AuctionStore | None = None, auction_name: str = "default"):
        self.state = state
        self.store = store
        self.auction_name = auction_name

    @classmethod
    def create(
        cls,
        *,
        year: int,
        team_names: Iterable[str],
        budget: int,
        players_df: pd.DataFrame,
        store: AuctionStore | None = None,
        auction_name: str = "default",
    ) -> "AuctionService":
        teams = {}
        for raw_name in team_names:
            name = str(raw_name).strip()
            if not name:
                continue
            if name in teams:
                raise AuctionError(f"Duplicated team name: {name}")
            teams[name] = Team(name=name, initial_budget=int(budget))

        if not teams:
            raise AuctionError("No teams provided")

        players = cls.players_from_quotazioni(players_df)
        state = AuctionState(year=int(year), teams=teams, players=players)
        state.events.append(AuctionEvent.now(action="create", note=f"Created auction with {len(teams)} teams"))
        service = cls(state=state, store=store, auction_name=auction_name)
        service.save_if_possible()
        return service

    @classmethod
    def load_or_create(
        cls,
        *,
        year: int,
        team_names: Iterable[str],
        budget: int,
        players_df: pd.DataFrame,
        store: AuctionStore,
        auction_name: str = "default",
    ) -> "AuctionService":
        if store.exists(year, auction_name):
            return cls(state=store.load(year, auction_name), store=store, auction_name=auction_name)
        return cls.create(
            year=year,
            team_names=team_names,
            budget=budget,
            players_df=players_df,
            store=store,
            auction_name=auction_name,
        )

    @staticmethod
    def players_from_quotazioni(players_df: pd.DataFrame) -> dict[str, AuctionPlayer]:
        players = {}
        for row in players_df.to_dict("records"):
            name = row.get("nome")
            if pd.isna(name) or not str(name).strip():
                continue
            name = str(name).strip()
            players[name] = AuctionPlayer(
                name=name,
                role=_none_if_na(row.get("ruolo")),
                real_team=_none_if_na(row.get("squadra")),
                url=_none_if_na(row.get("url")),
                qi=_none_if_na(row.get("QI")),
                qa=_none_if_na(row.get("QA")),
                fvm=_none_if_na(row.get("FVM")),
            )
        return players

    def save_if_possible(self) -> Path | None:
        if self.store is None:
            return None
        return self.store.save(self.state, self.auction_name)

    def assign_player(self, player_name: str, team_name: str, price: int) -> None:
        player = self._player(player_name)
        team = self._team(team_name)
        price = int(price)

        if price <= 0:
            raise AuctionError("Price must be positive")
        if not player.available:
            raise AuctionError(f"Player already assigned: {player.name} -> {player.owner} ({player.price})")
        if team.remaining_budget < price:
            raise AuctionError(f"Not enough budget for {team.name}: remaining {team.remaining_budget}, price {price}")

        player.owner = team.name
        player.price = price
        team.spent += price
        self.state.events.append(AuctionEvent.now(action="assign", player=player.name, team=team.name, price=price))
        self.save_if_possible()

    def release_player(self, player_name: str) -> None:
        player = self._player(player_name)
        if player.available:
            raise AuctionError(f"Player is already available: {player.name}")

        old_team = self._team(str(player.owner))
        old_price = int(player.price or 0)
        old_team.spent -= old_price
        player.owner = None
        player.price = None
        self.state.events.append(
            AuctionEvent.now(
                action="release",
                player=player.name,
                previous_team=old_team.name,
                previous_price=old_price,
            )
        )
        self.save_if_possible()

    def edit_price(self, player_name: str, new_price: int) -> None:
        player = self._player(player_name)
        if player.available:
            raise AuctionError(f"Cannot edit price of available player: {player.name}")
        new_price = int(new_price)
        if new_price <= 0:
            raise AuctionError("New price must be positive")

        team = self._team(str(player.owner))
        old_price = int(player.price or 0)
        delta = new_price - old_price
        if team.remaining_budget < delta:
            raise AuctionError(f"Not enough budget for price edit: remaining {team.remaining_budget}, delta {delta}")

        team.spent += delta
        player.price = new_price
        self.state.events.append(
            AuctionEvent.now(
                action="edit_price",
                player=player.name,
                team=team.name,
                price=new_price,
                previous_price=old_price,
            )
        )
        self.save_if_possible()

    def undo_last(self) -> None:
        if not self.state.events:
            raise AuctionError("No event to undo")

        event = self.state.events.pop()
        if event.action == "create":
            self.state.events.append(event)
            raise AuctionError("Cannot undo auction creation")

        if event.action == "assign":
            player = self._player(str(event.player))
            team = self._team(str(event.team))
            if player.owner == team.name:
                team.spent -= int(player.price or 0)
                player.owner = None
                player.price = None

        elif event.action == "release":
            player = self._player(str(event.player))
            team = self._team(str(event.previous_team))
            price = int(event.previous_price or 0)
            if team.remaining_budget < price:
                self.state.events.append(event)
                raise AuctionError("Cannot undo release: budget would become negative")
            player.owner = team.name
            player.price = price
            team.spent += price

        elif event.action == "edit_price":
            player = self._player(str(event.player))
            team = self._team(str(player.owner))
            old_price = int(event.previous_price or 0)
            current_price = int(player.price or 0)
            team.spent += old_price - current_price
            player.price = old_price

        else:
            self.state.events.append(event)
            raise AuctionError(f"Unsupported undo action: {event.action}")

        self.state.events.append(
            AuctionEvent.now(
                action="undo",
                player=event.player,
                team=event.team,
                price=event.price,
                note=f"Undid {event.action}",
            )
        )
        self.save_if_possible()

    def teams_table(self) -> pd.DataFrame:
        rows = []
        for team in self.state.teams.values():
            roster = [p for p in self.state.players.values() if p.owner == team.name]
            rows.append({
                "team": team.name,
                "initial_budget": team.initial_budget,
                "spent": team.spent,
                "remaining_budget": team.remaining_budget,
                "players": len(roster),
                "P": sum(1 for p in roster if p.role == "P"),
                "D": sum(1 for p in roster if p.role == "D"),
                "C": sum(1 for p in roster if p.role == "C"),
                "A": sum(1 for p in roster if p.role == "A"),
            })
        return pd.DataFrame(rows).sort_values("team").reset_index(drop=True)

    def players_table(self) -> pd.DataFrame:
        rows = []
        for player in self.state.players.values():
            rows.append({
                "nome": player.name,
                "ruolo": player.role,
                "squadra": player.real_team,
                "QI": player.qi,
                "QA": player.qa,
                "FVM": player.fvm,
                "owner": player.owner,
                "price": player.price,
                "available": player.available,
                "url": player.url,
            })
        return pd.DataFrame(rows).sort_values(["available", "ruolo", "nome"], ascending=[False, True, True]).reset_index(drop=True)

    def roster_table(self, team_name: str) -> pd.DataFrame:
        team = self._team(team_name)
        rows = [p for p in self.state.players.values() if p.owner == team.name]
        return pd.DataFrame([
            {
                "nome": p.name,
                "ruolo": p.role,
                "squadra": p.real_team,
                "price": p.price,
                "QA": p.qa,
                "FVM": p.fvm,
            }
            for p in rows
        ]).sort_values(["ruolo", "price", "nome"], ascending=[True, False, True]).reset_index(drop=True)

    def events_table(self) -> pd.DataFrame:
        return pd.DataFrame([event.to_dict() for event in self.state.events])

    def _team(self, team_name: str) -> Team:
        if team_name not in self.state.teams:
            raise AuctionError(f"Unknown team: {team_name}")
        return self.state.teams[team_name]

    def _player(self, player_name: str) -> AuctionPlayer:
        if player_name not in self.state.players:
            raise AuctionError(f"Unknown player: {player_name}")
        return self.state.players[player_name]


def _none_if_na(value):
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value
