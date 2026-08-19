# Fantastat Local Web Dashboard

## Build database

```bash
fantastat builddb --cache cache --replace
```

or:

```bash
python src/fantastat/builder.py --cache cache --replace
```

## Run web app

```bash
cd web
pip install -r ../requirements.txt
python app.py
```

Open:

```text
http://localhost:5000
```

## Global Last Days

The topbar contains:

- season selector
- `Last days`, default `38`

The backend computes a rolling matchday window across seasons. If selected season 2027 has no FINISHED matchdays yet and `Last days = 38`, the app uses 2026 MD1..38. After 2027 MD1 is FINISHED, the app uses 2026 MD2..38 plus 2027 MD1. Dashboard, player and comparison views all use this same global window.
