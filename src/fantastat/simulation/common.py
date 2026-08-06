from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from fantastat.analytics.views import played_rows, scheduled_rows

EVENT_METRICS = {"scoredGoals", "assists", "yellowCards", "redCards", "ownGoals"}

def num(df: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(df[name], errors="coerce") if name in df else pd.Series(np.nan, index=df.index, dtype=float)

def venue(df: pd.DataFrame) -> pd.Series:
    active = df.get("active_team", pd.Series(index=df.index, dtype=object)).astype("string")
    home = df.get("team_home", pd.Series(index=df.index, dtype=object)).astype("string")
    away = df.get("team_away", pd.Series(index=df.index, dtype=object)).astype("string")
    return pd.Series(np.select([active.eq(home), active.eq(away)], ["home", "away"], default="unknown"), index=df.index)

def prepare_history(frames: list[pd.DataFrame], last_n: int | None) -> pd.DataFrame:
    rows = []
    for df in frames:
        p = played_rows(df)
        p["venue"] = venue(p)
        rows.append(p)
    out = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    if last_n is not None: out = out.tail(last_n)
    return out

def prepare_future(df: pd.DataFrame) -> pd.DataFrame:
    out = scheduled_rows(df)
    out["venue"] = venue(out)
    cols = [c for c in ("giornata", "match_date", "match_time", "team_home", "team_away", "active_team", "venue", "stadium", "calendar_match_status") if c in out]
    return out[cols].reset_index(drop=True)

def metric_arrays(df: pd.DataFrame, metrics: tuple[str, ...]) -> dict[str, np.ndarray]:
    result = {}
    for m in metrics:
        values = num(df, m)
        if m in EVENT_METRICS: values = values.fillna(0)
        result[m] = values.to_numpy(float)
    return result

def summarise(samples: dict[str, np.ndarray], current: dict[str, float], quantiles: tuple[float, ...]) -> dict[str, Any]:
    out = {}
    for metric, future in samples.items():
        final = future + current.get(metric, 0.0)
        valid = final[np.isfinite(final)]
        out[metric] = {
            "current": float(current.get(metric, 0.0)),
            "future_mean": float(np.nanmean(future)) if np.isfinite(future).any() else None,
            "final_mean": float(valid.mean()) if valid.size else None,
            "final_std": float(valid.std(ddof=1)) if valid.size > 1 else None,
            "quantiles": {f"p{int(q*100):02d}": float(np.quantile(valid, q)) if valid.size else None for q in quantiles},
        }
    return out
