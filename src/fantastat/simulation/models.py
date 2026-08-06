from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

ModelName = Literal["iid_bootstrap", "markov_memory"]

@dataclass(frozen=True)
class ForecastConfig:
    model: ModelName = "iid_bootstrap"
    simulations: int = 10_000
    seed: int | None = None
    history_years: tuple[int, ...] = ()
    last_n_played: int | None = None
    venue_conditioning: bool = True
    memory: int = 2
    state_metric: str = "fantavoto"
    state_edges: tuple[float, ...] = (6.0, 6.5, 7.5)
    laplace: float = 1.0
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
    metrics: tuple[str, ...] = ("scoredGoals", "assists", "yellowCards", "redCards", "fantavoto", "voto")

    def validate(self) -> None:
        if not 100 <= self.simulations <= 200_000: raise ValueError("simulations must be between 100 and 200000")
        if not 1 <= self.memory <= 5: raise ValueError("memory must be between 1 and 5")
        if self.last_n_played is not None and self.last_n_played < 1: raise ValueError("last_n_played must be >= 1")
        if self.laplace <= 0: raise ValueError("laplace must be > 0")

@dataclass
class FittedModelInfo:
    model: str
    training_rows: int
    future_fixtures: int
    warnings: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
