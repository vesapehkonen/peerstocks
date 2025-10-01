#!/usr/bin/env python3
import argparse
import json
import os
import sys

import fetch_earnings
import fetch_prices
import fetch_stock_metadata
from config import settings
from opensearchpy import OpenSearch, helpers

DEFAULT_EARNINGS_INDEX = "earnings_data"
DEFAULT_PRICES_INDEX = "stock_prices"
DEFAULT_METADATA_INDEX = "stock_metadata"
CONNECT_TIMEOUT = 3


def os_client() -> OpenSearch:
    auth = None
    if settings.OS_USER and settings.OS_PASS:
        auth = (settings.OS_USER, settings.OS_PASS.get_secret_value())

    client = OpenSearch(
        hosts=[str(settings.OS_HOST)],
        http_auth=auth,
        timeout=CONNECT_TIMEOUT,
        max_retries=3,
        retry_on_timeout=True,
        verify_certs=False,
        ssl_show_warn=False,
    )
    return client


def actions_from_ndjson(path):
    with open(path, "r") as f:
        while True:
            meta = f.readline()
            if not meta: break
            src = f.readline()
            if not src: break
            meta_obj = json.loads(meta)
            op = next(iter(meta_obj))
            _id = meta_obj[op].get("_id")
            yield {"_op_type": "index", "_id": _id, "_source": json.loads(src)}


def seed(tickers, start_date, end_date, polygon_api_key, run_summary):
    client = os_client()

    prices_out = "prices_seed.ndjson"
    earnings_out = "earnings_seed.ndjson"
    metadata_out = "metadata_seed.ndjson"

    print(f"[SEED] Prices {tickers} {start_date}..{end_date}")
    fetch_prices.fetch_prices(tickers, start_date, end_date, output_file=prices_out)
    print(f"[INDEX] {prices_out} -> {DEFAULT_PRICES_INDEX}")
    helpers.bulk(client, actions_from_ndjson(prices_out), index=DEFAULT_PRICES_INDEX)

    print(f"[SEED] Earnings {tickers} {start_date}..{end_date}")
    if not polygon_api_key:
        polygon_api_key = settings.POLYGON_API_KEY.get_secret_value()
    if not polygon_api_key:
        raise SystemExit("Missing Polygon API key (set POLYGON_API_KEY or pass --api-key).")
    fetch_earnings.fetch_earnings(tickers, start_date, end_date, polygon_api_key, earnings_out)
    print(f"[INDEX] {earnings_out} -> {DEFAULT_EARNINGS_INDEX}")
    helpers.bulk(client, actions_from_ndjson(earnings_out), index=DEFAULT_EARNINGS_INDEX)

    print(f"[SEED] Metadata {tickers}")
    fetch_stock_metadata.fetch_stock_metadata(tickers, polygon_api_key, metadata_out)
    print(f"[INDEX] {metadata_out} -> {DEFAULT_METADATA_INDEX}")
    helpers.bulk(client, actions_from_ndjson(metadata_out), index=DEFAULT_METADATA_INDEX)

    if run_summary:
        print("[SUMMARY] update_stock_summary.py …")
        os.system(f"{sys.executable} update_stock_summary.py {tickers}")


def load_tickers(arg: str) -> str:
    # First, try to treat it as a file path (without uppercasing the path)
    if os.path.isfile(arg):
        with open(arg) as f:
            syms = [ln.strip() for ln in f if ln.strip()]
        return ",".join(s.upper() for s in syms)

    # If it *looks* like a path but isn't a file, fail fast
    if os.path.sep in arg:
        raise SystemExit(f"Ticker file not found: {arg}")

    # Otherwise treat it as a comma-separated list of tickers
    return ",".join(t.strip().upper() for t in arg.split(",") if t.strip())


from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def parse_args():
    p = argparse.ArgumentParser(description="Seed new tickers with historical prices & earnings.")
    p.add_argument("tickers", help="Comma-separated tickers or path to a text file with one ticker per line.")
    p.add_argument("start_date", nargs="?", help="YYYY-MM-DD (historical start). Defaults to ~10 years ago.")
    p.add_argument("end_date", nargs="?", help="YYYY-MM-DD (historical end). Defaults to today.")
    p.add_argument("--api-key", default=os.getenv("POLYGON_API_KEY", ""))
    p.add_argument("--skip-summary", action="store_true")

    args = p.parse_args()

    def to_date(x):
        if x is None:
            return None
        if isinstance(x, date) and not isinstance(x, datetime):
            return x
        if isinstance(x, datetime):
            return x.date()
        # assume string YYYY-MM-DD
        return date.fromisoformat(str(x).strip())

    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()

    end = to_date(args.end_date) or today
    start = to_date(args.start_date) or (end - timedelta(days=3650))  # ~10 years

    if start > end:
        p.error(f"start_date ({start.isoformat()}) cannot be after end_date ({end.isoformat()}).")

    # normalize back to strings for downstream funcs
    args.start_date = start.isoformat()
    args.end_date = end.isoformat()
    return args


def main():
    a = parse_args()
    tickers_csv = load_tickers(a.tickers)
    seed(tickers_csv, a.start_date, a.end_date, a.api_key, not a.skip_summary)


if __name__ == "__main__":
    main()
