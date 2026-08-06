import json
from pathlib import Path

import pandas as pd
import pytest

from fantastat import CacheRepository, FantacalcioService


def build_cache(root: Path):
    pd.DataFrame([
        {"nome": "Mario Rossi", "ruolo": "A", "squadra": "Inter", "QI": 20, "QA": 22, "FVM": 30, "url": "u"},
        {"nome": "Luca Bianchi", "ruolo": "D", "squadra": "Milan", "QI": 8, "QA": 9, "FVM": 12, "url": "v"},
    ]).to_csv(root / "quotazioni2026.csv", index=False)
    payload = {
        "Mario Rossi": {"records": [
            {"giornata": 1, "active_team": "Inter", "team_home": "Inter", "team_away": "Milan", "score_home": 2, "score_away": 1, "win": 1, "voto": 7, "fantavoto": 10, "scoredGoals": 1, "assists": 0},
            {"giornata": 2, "active_team": "Inter", "team_home": "Roma", "team_away": "Inter", "score_home": 0, "score_away": 0, "win": 0, "voto": 6, "fantavoto": 6, "scoredGoals": 0, "assists": 0},
        ], "attrs": {"team": "Inter", "bridge": {"playerId": 1}}},
        "Luca Bianchi": {"records": [
            {"giornata": 1, "active_team": "Milan", "team_home": "Inter", "team_away": "Milan", "score_home": 2, "score_away": 1, "win": -1, "voto": 5.5, "fantavoto": 5.5, "scoredGoals": 0, "assists": 0}
        ], "attrs": {"team": "Milan", "bridge": {"playerId": 2}}},
    }
    (root / "stats2026.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def service(tmp_path):
    build_cache(tmp_path)
    return FantacalcioService(CacheRepository(tmp_path))


def test_aggregate(service):
    result = service.player_aggregate("mario rossi", year=2026)
    assert result["metrics"]["voto"]["mean"] == 6.5
    assert result["metrics"]["scoredGoals"]["sum"] == 1.0


def test_summary(service):
    players = service.players_summary(2026)
    mario = next(row for row in players if row["nome"] == "Mario Rossi")
    assert mario["fantavoto_medio"] == 8.0
    assert mario["gol_per_presenza"] == 0.5


def test_distribution_home(service):
    result = service.player_distribution("Mario Rossi", "scoredGoals", year=2026, condition="home")
    assert result["sample_size"] == 1
    assert result["distribution"][0]["probability"] == 1.0


def test_global_calendar_deduplicates_fixture(service):
    fixtures = service.league_calendar(2026)
    assert len(fixtures) == 2
