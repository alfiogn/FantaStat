from __future__ import annotations
from .repository import CacheRepository
from .simulation import ForecastConfig, SeasonForecastEngine

class FantastatService:
    def __init__(self, repository: CacheRepository):
        self.repo = repository
        self.engine = SeasonForecastEngine()

    def forecast(self, player: str, year: int, config: ForecastConfig):
        canonical, target = self.repo.player(year, player)
        years = list(config.history_years) or [y for y in self.repo.list_years() if y <= year]
        histories = []
        used_years = []
        for y in years:
            try:
                _, df = self.repo.player(y, canonical)
                histories.append(df); used_years.append(y)
            except Exception:
                continue
        if not histories: raise ValueError("No player history available")
        result = self.engine.forecast(canonical, target, histories, config)
        result["training_years"] = used_years
        return result
