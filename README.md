# Fantastat 0.2

Backend analitico e Season Forecast compatibile con il modello a timeline completa:

- `record_type=player_page`: riga reale, usata nei calcoli
- `record_type=calendar_placeholder`: partita programmata, mai usata nel fitting
- `played` e `is_placeholder` sono normalizzati, ma `record_type` resta discriminante principale
- pagine giocatore vuote sono valide; una simulazione senza storico restituisce `422`, non corrompe i risultati

## Installazione e avvio

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
fantastat-api --cache-dir /path/cache --host 0.0.0.0 --port 8000
pytest -q
```

Swagger: `http://localhost:8000/docs`

## API Season Forecast

```http
GET  /api/v1/forecast/models
GET  /api/v1/players/{player}/seasons/{year}/forecast/default
POST /api/v1/players/{player}/seasons/{year}/forecast
```

Esempio body:

```json
{
  "model": "markov_memory",
  "simulations": 10000,
  "seed": 42,
  "history_years": [2024, 2025, 2026],
  "last_n_played": null,
  "venue_conditioning": true,
  "memory": 2,
  "state_metric": "fantavoto",
  "state_edges": [6.0, 6.5, 7.5],
  "laplace": 1.0,
  "quantiles": [0.1, 0.5, 0.9],
  "metrics": ["scoredGoals", "assists", "fantavoto", "voto"]
}
```

## Modelli

### IID bootstrap

Campiona righe storiche complete, non metriche indipendenti. Mantiene quindi la dipendenza empirica tra gol, assist, voto, fantavoto e cartellini. Usa pool casa/trasferta e fallback totale se il pool è troppo piccolo.

### Markov con memoria

Discretizza `fantavoto` negli stati `no_vote`, `low`, `mid`, `high`, `elite`. Stima transizioni di ordine `k`. Durante la simulazione usa backoff verso contesti più corti e smoothing di Laplace. Le emissioni sono righe storiche complete dello stato simulato.

Questo è Markov Monte Carlo forward, non MCMC bayesiano. Non usa Metropolis-Hastings e non campiona una posterior.

## Frontend

`web/src/features/season-forecast` contiene una feature React isolata:

- `types.ts`
- `api.ts`
- `SeasonForecastPage.tsx`

È intenzionalmente priva di dipendenze UI e charting. Può essere montata nella dashboard esistente e sostituita gradualmente con Mantine/Recharts.
