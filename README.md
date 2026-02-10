# Dynasty Baseball Projections — Web App

A web application for browsing 20-year MLB dynasty baseball projections (2026–2045) and generating personalized dynasty rankings with custom league settings.

## Features

- **Projections Explorer** — Browse, search, filter, and sort hitter/pitcher projections across 20 seasons
- **Dynasty Value Calculator** — Configure your league settings (teams, roster, categories, IP caps) and generate Monte Carlo–based dynasty rankings
- **Free & ad-free** — No accounts, no paywalls

## Architecture

```
dynasty-site/
├── backend/
│   ├── app.py                          # FastAPI application
│   └── dynasty_roto_values.py          # Core calculation engine
├── frontend/
│   └── index.html                      # Single-page React app
├── data/
│   ├── Dynasty Baseball Projections.xlsx
│   ├── bat.json                        # Pre-processed hitter data
│   ├── pitch.json                      # Pre-processed pitcher data
│   └── meta.json                       # Filter options metadata
├── Dockerfile
├── requirements.txt
└── README.md
```

## Local Development

### Prerequisites
- Python 3.10+

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the dev server
uvicorn backend.app:app --reload --port 8000
```

Then open http://localhost:8000

### Updating Projections

When you update the Excel file, re-run the preprocessing to regenerate the JSON data files:

```bash
python preprocess.py
```

## Deployment

### Docker
```bash
docker build -t dynasty-projections .
docker run -p 8000:8000 dynasty-projections
```

### Railway / Render / Fly.io
All three support Dockerfiles out of the box:

1. Push this repo to GitHub
2. Connect the repo to your hosting provider
3. It will auto-detect the Dockerfile and deploy

**Railway** (recommended for simplicity):
- Free tier: 500 hours/month, 512 MB RAM — plenty for this app
- Just connect your GitHub repo and deploy

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/meta` | Filter options (teams, years, positions) |
| GET | `/api/projections/bat` | Hitter projections (query params: player, team, year, pos) |
| GET | `/api/projections/pitch` | Pitcher projections (same query params) |
| POST | `/api/calculate` | Run dynasty value calculator (JSON body with league settings) |

## Next Steps

Some ideas for future development:

- **Player profile pages** — individual player pages with year-by-year projection charts
- **Comparison tool** — side-by-side player comparisons
- **League mode** — add the full custom league settings (SP/RP/P slots, OPS, SVH categories)
- **Export** — download rankings as CSV or Excel
- **Projection freshness indicators** — show when each player's projection was last updated
- **Mobile optimization** — responsive improvements for phone-sized screens
