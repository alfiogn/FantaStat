from __future__ import annotations
import pandas as pd

PLAYER_PAGE = "player_page"
PLACEHOLDER = "calendar_placeholder"


def normalise_provenance(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical record_type, played and is_placeholder columns.

    New caches are authoritative. Legacy fallback exists only to keep old seasons readable.
    It never infers played from vote availability when record_type or played is present.
    """
    out = df.copy()
    if "record_type" in out:
        rt = out["record_type"].astype("string")
        out["played"] = rt.eq(PLAYER_PAGE)
        out["is_placeholder"] = rt.eq(PLACEHOLDER)
    elif "played" in out:
        out["played"] = out["played"].fillna(False).astype(bool)
        out["is_placeholder"] = ~out["played"]
        out["record_type"] = out["played"].map({True: PLAYER_PAGE, False: PLACEHOLDER})
    elif "is_placeholder" in out:
        out["is_placeholder"] = out["is_placeholder"].fillna(False).astype(bool)
        out["played"] = ~out["is_placeholder"]
        out["record_type"] = out["is_placeholder"].map({True: PLACEHOLDER, False: PLAYER_PAGE})
    else:
        # Legacy historical cache only. Rows from the old player-page-only model are real.
        out["record_type"] = PLAYER_PAGE
        out["played"] = True
        out["is_placeholder"] = False
    return out


def played_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = normalise_provenance(df)
    return out.loc[out["record_type"].eq(PLAYER_PAGE)].copy()


def scheduled_rows(df: pd.DataFrame) -> pd.DataFrame:
    out = normalise_provenance(df)
    return out.loc[out["record_type"].eq(PLACEHOLDER)].copy()


def full_timeline(df: pd.DataFrame) -> pd.DataFrame:
    out = normalise_provenance(df)
    keys = [c for c in ("giornata", "match_date", "match_time") if c in out]
    return out.sort_values(keys, kind="stable") if keys else out


def last_n_played(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if n < 1:
        raise ValueError("n must be >= 1")
    return full_timeline(played_rows(df)).tail(n)


def next_n_fixtures(df: pd.DataFrame, n: int | None = None) -> pd.DataFrame:
    out = full_timeline(scheduled_rows(df))
    return out if n is None else out.head(n)
