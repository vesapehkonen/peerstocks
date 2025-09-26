if [ "$#" -ne 1 ]; then
   echo "Usage $0 /path/to/ticker/file"
   exit 1
]
. .env
docker compose -f compose.${APP_ENV}.yml run --rm --no-deps -v "$tickers_file:/app/tickers.txt" ingest fetch_prices_wrapper.py /app/tickers.txt --run-summary
