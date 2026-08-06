from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from fantastat.analytics.views import played_rows
from .common import EVENT_METRICS, num, prepare_future, prepare_history
from .iid import IIDBootstrapSimulator
from .markov import MarkovMemorySimulator
from .models import ForecastConfig

class SeasonForecastEngine:
    def forecast(self, player: str, target: pd.DataFrame, histories: list[pd.DataFrame], cfg: ForecastConfig) -> dict[str, Any]:
        cfg.validate()
        history = prepare_history(histories, cfg.last_n_played)
        future = prepare_future(target)
        current_df = played_rows(target)
        current = {}
        for m in cfg.metrics:
            v = num(current_df, m)
            current[m] = float(v.fillna(0).sum()) if m in EVENT_METRICS else float(v.mean()) if v.notna().any() else 0.0
        simulator = IIDBootstrapSimulator() if cfg.model == "iid_bootstrap" else MarkovMemorySimulator()
        samples, info = simulator.run(history, future, cfg)
        metrics = {}
        for m, future_samples in samples.items():
            if m in EVENT_METRICS:
                final = future_samples + current[m]
            else:
                # Combine simulated future mean with current observed mean by match counts.
                n_current = int(num(current_df, m).notna().sum())
                n_future = len(future)
                final = (current[m] * n_current + future_samples * n_future) / max(n_current + n_future, 1)
            valid = final[np.isfinite(final)]
            metrics[m] = {
                "current": current[m],
                "future_mean": float(np.nanmean(future_samples)) if np.isfinite(future_samples).any() else None,
                "final_mean": float(valid.mean()) if valid.size else None,
                "final_std": float(valid.std(ddof=1)) if valid.size > 1 else None,
                "quantiles": {f"p{int(q*100):02d}": float(np.quantile(valid, q)) if valid.size else None for q in cfg.quantiles},
            }
        fixtures = future.where(pd.notna(future), None).to_dict(orient="records")
        return {
            "player": player,
            "model": info.model,
            "configuration": cfg.__dict__,
            "fit": info.__dict__,
            "metrics": metrics,
            "fixtures": fixtures,
            "disclaimer": "Forecast statistico esplorativo. It does not model injuries, transfers, tactical changes or line-up decisions unless encoded in observed history.",
        }
