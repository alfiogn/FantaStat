from __future__ import annotations
import numpy as np
import pandas as pd
from .common import EVENT_METRICS, metric_arrays, num
from .models import ForecastConfig, FittedModelInfo

class IIDBootstrapSimulator:
    """Non-parametric Monte Carlo. Samples historical match rows as vectors.

    Sampling the whole row preserves empirical dependence between vote, goals,
    assists and cards. Venue-specific pools back off to the full pool.
    """
    def run(self, history: pd.DataFrame, future: pd.DataFrame, cfg: ForecastConfig):
        if history.empty: raise ValueError("No played rows available for fitting")
        rng = np.random.default_rng(cfg.seed)
        arrays = metric_arrays(history, cfg.metrics)
        pools = {v: np.flatnonzero(history["venue"].eq(v).to_numpy()) for v in ("home", "away")}
        full = np.arange(len(history))
        totals = {m: np.zeros(cfg.simulations, dtype=float) for m in cfg.metrics}
        counts = {m: np.zeros(cfg.simulations, dtype=int) for m in cfg.metrics}
        warnings = []
        for _, fixture in future.iterrows():
            pool = pools.get(fixture.get("venue"), full) if cfg.venue_conditioning else full
            if pool.size < 5:
                pool = full
                if "Sparse venue pool: fallback to all played rows" not in warnings: warnings.append("Sparse venue pool: fallback to all played rows")
            draw = rng.choice(pool, size=cfg.simulations, replace=True)
            for m, values in arrays.items():
                x = values[draw]
                valid = np.isfinite(x)
                if m in EVENT_METRICS: x = np.nan_to_num(x, nan=0.0); valid[:] = True
                totals[m] += np.where(valid, x, 0.0)
                counts[m] += valid
        # Means such as vote/fantavoto must be season means, not sums.
        for m in cfg.metrics:
            if m not in EVENT_METRICS:
                totals[m] = np.divide(totals[m], counts[m], out=np.full(cfg.simulations, np.nan), where=counts[m] > 0)
        info = FittedModelInfo("iid_bootstrap", len(history), len(future), warnings)
        return totals, info
