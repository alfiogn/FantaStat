from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .repository import CacheNotFoundError, CacheRepository, PlayerNotFoundError
from .service import FantastatService
from .simulation import ForecastConfig

class ForecastRequest(BaseModel):
    model: str = Field(default="iid_bootstrap", pattern="^(iid_bootstrap|markov_memory)$")
    simulations: int = Field(default=10_000, ge=100, le=200_000)
    seed: int | None = None
    history_years: list[int] = []
    last_n_played: int | None = Field(default=None, ge=1)
    venue_conditioning: bool = True
    memory: int = Field(default=2, ge=1, le=5)
    state_metric: str = "fantavoto"
    state_edges: list[float] = [6.0, 6.5, 7.5]
    laplace: float = Field(default=1.0, gt=0)
    quantiles: list[float] = [0.1, 0.5, 0.9]
    metrics: list[str] = ["scoredGoals", "assists", "yellowCards", "redCards", "fantavoto", "voto"]

    def to_config(self) -> ForecastConfig:
        return ForecastConfig(**{**self.model_dump(), "history_years": tuple(self.history_years), "state_edges": tuple(self.state_edges), "quantiles": tuple(self.quantiles), "metrics": tuple(self.metrics)})

def create_app(cache_dir: str | Path | None = None) -> FastAPI:
    service = FantastatService(CacheRepository(cache_dir or os.getenv("FANTASTAT_CACHE_DIR", "cache")))
    app = FastAPI(title="Fantastat API", version="0.2.0")

    @app.get("/health")
    def health(): return {"status": "ok", "years": service.repo.list_years()}

    @app.get("/api/v1/forecast/models")
    def models():
        return {"models": [
            {"id": "iid_bootstrap", "label": "Monte Carlo bootstrap", "supports": ["venue_conditioning"]},
            {"id": "markov_memory", "label": "Markov con memoria", "supports": ["memory", "state_metric", "state_edges", "laplace"]},
        ]}

    @app.post("/api/v1/players/{player}/seasons/{year}/forecast")
    def forecast(player: str, year: int, body: ForecastRequest):
        try: return service.forecast(player, year, body.to_config())
        except (CacheNotFoundError, PlayerNotFoundError) as exc: raise HTTPException(404, str(exc))
        except ValueError as exc: raise HTTPException(422, str(exc))

    @app.get("/api/v1/players/{player}/seasons/{year}/forecast/default")
    def default_forecast(player: str, year: int):
        try: return service.forecast(player, year, ForecastConfig())
        except (CacheNotFoundError, PlayerNotFoundError) as exc: raise HTTPException(404, str(exc))
        except ValueError as exc: raise HTTPException(422, str(exc))

    return app

app = create_app()
