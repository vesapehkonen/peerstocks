
# PeerStocks

[![Live Demo](https://img.shields.io/badge/demo-online-green.svg)](https://peerstocks.example.com)

A peer comparison dashboard for equities. Add multiple tickers and compare their *Price (indexed)*, *P/E*, and *EPS (TTM)* at a glance.  
Backend API + ingest jobs + OpenSearch for data; React frontend for the UI.

![PeerStocks screenshot](./peerstocks.png)

## Demo

🚀 Try it live here: [peerstocks.example.com](https://peerstocks.example.com)


## Features
- Compare multiple tickers side‑by‑side
- Charts: Price (indexed), P/E, and EPS (TTM)
- Per‑company mini‑charts and a sortable summary table
- Lightweight ingestion jobs to seed symbols and fetch updates
- Dockerized services for easy local dev and production

## Requirements
- Docker & Docker Compose
- Node 18+ (only if running the dev frontend with `npm start`)

## 1) Configure environment
Copy the sample env files and fill in the required values. (See the sample files for the full list.)

```bash
# development
cp env/development/backend.env.sample   env/development/backend.env
cp env/development/ingest.env.sample    env/development/ingest.env

# production
cp env/production/backend.env.sample    env/production/backend.env
cp env/production/ingest.env.sample     env/production/ingest.env
```

Common variables (see samples for exact names): OpenSearch connection (host/URL, user, password), API keys for data providers (e.g. earnings/prices), and any app‑specific secrets.

## 2) Build images
```bash
docker build -t backend:latest   backend
docker build -t ingest:latest    ingest
docker build -t frontend:latest  --build-arg REACT_APP_API_BASE_URL=/api frontend
```

## 3) Define environment variables
```bash
export OPENSEARCH_DATA_DIR=<path-to-opensearch-data>
export OPENSEARCH_LOG_DIR=<path-to-opensearch-logs>
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='<strong-password>' # only for production
```

## 4) Run (production)
```bash
docker compose -f compose.prod.yml up
# open: http://localhost
```

## 5) Run (development)
```bash
docker compose -f compose.dev.yml up
cd frontend && npm ci && npm start
# open: http://localhost:3000
```

## 6) Data ingestion

**Seed tickers** (choose dev or prod compose file):
```bash
docker compose -f compose.[dev/prod].yml run --rm --no-deps ingest \
  seed_new_tickers.py tickers.txt 2015-01-01 2026-01-01
```

**Fetch latest prices**
```bash
docker compose -f compose.[dev/prod].yml run --rm --no-deps ingest \
  fetch_prices_wrapper.py tickers.txt
```

**Fetch latest earnings**
```bash
docker compose -f compose.[dev/prod].yml run --rm --no-deps ingest \
  fetch_earnings_wrapper.py tickers.txt
```

## License

This project is licensed under the [MIT License](LICENSE).
