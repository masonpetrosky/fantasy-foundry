# Dynasty Baseball Projections — Web App

A web application for browsing 20-year MLB dynasty baseball projections (2026–2045) and generating personalized dynasty rankings with custom league settings.

## Production

- Live site: https://fantasy-foundry.com
- Hosting: Railway (Docker deploy from this repository)

## Features

- **Projections Explorer** — Browse, search, filter, sort, and paginate hitter/pitcher/combined projections across 20 seasons
- **Dynasty Value Calculator** — Configure your league settings (teams, roster, categories, IP caps) and generate Monte Carlo–based dynasty rankings
- **Efficient large-result loading** — Projection responses are gzip-compressed by the API, and the UI cancels stale in-flight requests during rapid filter changes
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

### Running Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Running Browser E2E Tests (Playwright)
```bash
# Install app + dev test dependencies
pip install -r requirements-dev.txt

# Install Playwright Chromium once
python -m playwright install chromium

# Run the pagination integration test
python -m unittest tests/test_e2e_projections_pagination.py
```

This test launches the app locally, selects `All Years` in the projections view, and verifies:
- the UI reports more than 5,000 projection rows
- the browser issued paginated API requests against `/api/projections/all`

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
- Current production custom domain: https://fantasy-foundry.com

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/meta` | Filter options (teams, years, positions) |
| GET | `/api/projections/all` | Combined hitter+pitcher rows (query params: player, team, year, years, pos, dynasty_years, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/bat` | Hitter projections (query params: player, team, year, years, pos, dynasty_years, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/pitch` | Pitcher projections (same query params as `/api/projections/bat`) |
| POST | `/api/calculate` | Run dynasty value calculator (JSON body with league settings) |

`years` accepts comma-separated years and inclusive ranges, for example `2026,2028-2030`.
If both `year` and `years` are provided, results use the intersection.
`dynasty_years` accepts comma-separated years and inclusive ranges, for example `2026,2028-2030`.
`pos` accepts one or more exact position tokens (comma, slash, or space separated), for example `SP,RP` or `1B/OF`.
`sort_dir` supports `asc` or `desc` and is applied server-side before pagination.
`sort_col` is validated server-side and returns HTTP 422 when unsupported for that endpoint.

For `/api/projections/all`, stat collisions are explicit:
- `H`, `HR`, `BB` are hitter stats
- `PitH`, `PitHR`, `PitBB` are pitcher stats

Identity fields are included end-to-end:
- `PlayerKey`: deterministic normalized player key
- `PlayerEntityKey`: disambiguated key for same-name collisions
- `DynastyMatchStatus`: `matched`, `no_unique_match`, or `missing` when dynasty values are attached

## Next Steps

Some ideas for future development:

- **Player profile pages** — individual player pages with year-by-year projection charts
- **Comparison tool** — side-by-side player comparisons
- **League mode** — add the full custom league settings (SP/RP/P slots, OPS, SVH categories)
- **Export** — download rankings as CSV or Excel
- **Projection freshness indicators** — show when each player's projection was last updated
- **Mobile optimization** — responsive improvements for phone-sized screens
