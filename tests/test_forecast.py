import json
import pandas as pd
from fantastat import CacheRepository, FantastatService
from fantastat.analytics.views import played_rows, scheduled_rows
from fantastat.simulation import ForecastConfig

def make_cache(tmp_path):
    real=[]
    for g, fv, goal, home in [(1,6.0,0,True),(2,7.5,1,False),(3,6.5,0,True),(4,8.0,1,False),(5,5.5,0,True),(6,7.0,0,False)]:
        real.append({"giornata":g,"record_type":"player_page","played":True,"is_placeholder":False,"active_team":"Inter","team_home":"Inter" if home else "Roma","team_away":"Roma" if home else "Inter","voto":fv-0.5,"fantavoto":fv,"scoredGoals":goal,"assists":0,"yellowCards":0,"redCards":0})
    future=[]
    for g in (7,8,9):
        future.append({"giornata":g,"record_type":"calendar_placeholder","played":False,"is_placeholder":True,"active_team":"Inter","team_home":"Inter","team_away":"Milan","status":"scheduled","voto":None,"fantavoto":None,"scoredGoals":0,"assists":0,"yellowCards":0,"redCards":0})
    payload={"Mario Rossi":{"records":real+future,"attrs":{"team":"Inter","calendar_season":"2025-26","calendar_placeholders_added":3}}}
    (tmp_path/"stats2026.json").write_text(json.dumps(payload),encoding="utf-8")

def test_views_do_not_pollute(tmp_path):
    make_cache(tmp_path); _,df=CacheRepository(tmp_path).player(2026,"Mario Rossi")
    assert len(played_rows(df))==6 and len(scheduled_rows(df))==3

def test_iid_is_reproducible(tmp_path):
    make_cache(tmp_path); s=FantastatService(CacheRepository(tmp_path)); c=ForecastConfig(simulations=1000,seed=42)
    a=s.forecast("Mario Rossi",2026,c); b=s.forecast("Mario Rossi",2026,c)
    assert a["metrics"]["scoredGoals"]==b["metrics"]["scoredGoals"]
    assert a["fit"]["future_fixtures"]==3

def test_markov_memory(tmp_path):
    make_cache(tmp_path); s=FantastatService(CacheRepository(tmp_path)); c=ForecastConfig(model="markov_memory",simulations=500,seed=4,memory=2)
    r=s.forecast("Mario Rossi",2026,c)
    assert r["model"]=="markov_memory" and r["metrics"]["fantavoto"]["final_mean"] is not None
