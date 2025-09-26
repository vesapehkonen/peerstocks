. .env
docker compose -f compose.${APP_ENV}.yml run --rm --no-deps  -v "$PWD/ingest:/app/ingest" ingest init_indices.py
