from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

CORE_METRICS = (
    "voto", "fantavoto", "voto_graph", "fantavoto_graph",
    "scoredGoals", "assists", "yellowCards", "redCards", "ownGoals",
    "bonus_graph", "malus_graph", "quotazione_classic", "quotazione_mantra",
    "win", "sub_in_minute", "sub_out_minute",
)
EVENT_METRICS = ("scoredGoals", "assists", "yellowCards", "redCards", "ownGoals")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def existing_metrics(frame: pd.DataFrame, requested: Iterable[str] | None = None) -> list[str]:
    candidates = list(requested) if requested else list(CORE_METRICS)
    return [metric for metric in candidates if metric in frame.columns]


def apply_window(frame: pd.DataFrame, last_n: int | None) -> pd.DataFrame:
    if last_n is None:
        return frame
    if last_n < 1:
        raise ValueError("last_n must be >= 1")
    sort_cols = [c for c in ("reference_year", "giornata") if c in frame.columns]
    ordered = frame.sort_values(sort_cols, kind="stable") if sort_cols else frame
    return ordered.tail(last_n)


def descriptive_statistics(frame: pd.DataFrame, metrics: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for metric in existing_metrics(frame, metrics):
        values = numeric(frame, metric)
        valid = values.dropna()
        count = int(valid.size)
        if count == 0:
            result[metric] = {"count": 0, "missing": int(values.isna().sum())}
            continue
        result[metric] = json_safe({
            "count": count,
            "missing": int(values.isna().sum()),
            "sum": float(valid.sum()),
            "mean": float(valid.mean()),
            "variance": float(valid.var(ddof=1)) if count > 1 else None,
            "std": float(valid.std(ddof=1)) if count > 1 else None,
            "min": float(valid.min()),
            "q25": float(valid.quantile(0.25)),
            "median": float(valid.median()),
            "q75": float(valid.quantile(0.75)),
            "max": float(valid.max()),
            "nonzero_rate": float(valid.ne(0).mean()),
        })
    return result


def venue_for_player(frame: pd.DataFrame) -> pd.Series:
    active = frame.get("active_team", pd.Series(index=frame.index, dtype=object)).astype("string")
    home = frame.get("team_home", pd.Series(index=frame.index, dtype=object)).astype("string")
    away = frame.get("team_away", pd.Series(index=frame.index, dtype=object)).astype("string")
    return pd.Series(np.select([active.eq(home), active.eq(away)], ["home", "away"], default="unknown"), index=frame.index)


def pmf(values: pd.Series) -> list[dict[str, Any]]:
    clean = values.dropna()
    if clean.empty:
        return []
    counts = clean.value_counts(dropna=False).sort_index()
    total = int(counts.sum())
    return [
        {"value": json_safe(value), "count": int(count), "probability": float(count / total)}
        for value, count in counts.items()
    ]


def distribution(frame: pd.DataFrame, metric: str, *, condition: str = "all", bins: int | None = None) -> dict[str, Any]:
    scoped = frame.copy()
    venue = venue_for_player(scoped)
    if condition in {"home", "away"}:
        scoped = scoped.loc[venue.eq(condition)]
    elif condition != "all":
        raise ValueError("condition must be all, home or away")
    values = numeric(scoped, metric).dropna()
    if values.empty:
        return {"metric": metric, "condition": condition, "sample_size": 0, "distribution": []}
    if bins and values.nunique() > bins:
        counts, edges = np.histogram(values.to_numpy(), bins=bins)
        total = int(counts.sum())
        rows = [
            {"left": float(edges[i]), "right": float(edges[i + 1]), "count": int(count), "probability": float(count / total)}
            for i, count in enumerate(counts)
        ]
    else:
        rows = pmf(values)
    return {"metric": metric, "condition": condition, "sample_size": int(values.size), "distribution": rows}


def records(frame: pd.DataFrame, columns: Iterable[str] | None = None) -> list[dict[str, Any]]:
    selected = frame.loc[:, [c for c in columns if c in frame.columns]] if columns else frame
    return json_safe(selected.astype(object).where(pd.notna(selected), None).to_dict(orient="records"))
