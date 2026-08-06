from __future__ import annotations
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
from .common import EVENT_METRICS, metric_arrays, num
from .models import ForecastConfig, FittedModelInfo

class MarkovMemorySimulator:
    """Order-k Markov Monte Carlo over observed performance states.

    This is not Bayesian MCMC. It is forward Monte Carlo from an estimated
    variable-order Markov chain. State transitions use Laplace smoothing and
    back off from order k to shorter contexts when the exact context is unseen.
    Emissions are bootstrapped as complete historical rows within each state.
    """
    def _states(self, history: pd.DataFrame, cfg: ForecastConfig) -> np.ndarray:
        x = num(history, cfg.state_metric).to_numpy(float)
        labels = np.array(["no_vote", "low", "mid", "high", "elite"], dtype=object)
        idx = np.digitize(x, np.asarray(cfg.state_edges), right=False) + 1
        idx[~np.isfinite(x)] = 0
        return labels[idx]

    def run(self, history: pd.DataFrame, future: pd.DataFrame, cfg: ForecastConfig):
        if history.empty: raise ValueError("No played rows available for fitting")
        rng = np.random.default_rng(cfg.seed)
        states = self._states(history, cfg)
        state_names = list(dict.fromkeys(states.tolist()))
        transition: dict[tuple[str, ...], Counter] = defaultdict(Counter)
        for i in range(1, len(states)):
            for order in range(1, min(cfg.memory, i) + 1):
                transition[tuple(states[i-order:i])][states[i]] += 1
        emissions = {s: np.flatnonzero(states == s) for s in state_names}
        arrays = metric_arrays(history, cfg.metrics)
        current_context = tuple(states[-cfg.memory:])
        contexts = np.tile(np.asarray(current_context, dtype=object), (cfg.simulations, 1))
        totals = {m: np.zeros(cfg.simulations) for m in cfg.metrics}
        counts = {m: np.zeros(cfg.simulations, dtype=int) for m in cfg.metrics}
        warnings = []
        for _ in range(len(future)):
            next_states = np.empty(cfg.simulations, dtype=object)
            for i in range(cfg.simulations):
                counter = None
                for order in range(min(cfg.memory, contexts.shape[1]), 0, -1):
                    c = transition.get(tuple(contexts[i, -order:]))
                    if c: counter = c; break
                if counter is None:
                    counter = Counter(states.tolist())
                weights = np.array([counter.get(s, 0) + cfg.laplace for s in state_names], float)
                next_states[i] = rng.choice(state_names, p=weights / weights.sum())
            for s in state_names:
                target = np.flatnonzero(next_states == s)
                if not target.size: continue
                draw = rng.choice(emissions[s], size=target.size, replace=True)
                for m, values in arrays.items():
                    x = values[draw]
                    valid = np.isfinite(x)
                    if m in EVENT_METRICS: x = np.nan_to_num(x, nan=0.0); valid[:] = True
                    totals[m][target] += np.where(valid, x, 0.0)
                    counts[m][target] += valid
            contexts = np.column_stack([contexts[:, 1:], next_states]) if contexts.shape[1] > 1 else next_states[:, None]
        for m in cfg.metrics:
            if m not in EVENT_METRICS:
                totals[m] = np.divide(totals[m], counts[m], out=np.full(cfg.simulations, np.nan), where=counts[m] > 0)
        if len(history) < 20: warnings.append("Short history for a memory model; transition estimates are unstable")
        return totals, FittedModelInfo("markov_memory", len(history), len(future), warnings, state_names)
