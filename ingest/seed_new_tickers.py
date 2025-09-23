#!/usr/bin/env python3
import os, sys, argparse, json, time
from opensearchpy import OpenSearch, helpers
import fetch_prices
import fetch_earnings

DEFAULT_EARNINGS_INDEX = "earnings_data"
DEFAULT_PRICES_INDEX = "stock_prices"


def os_client():
    host = os.getenv("OS_HOST")
    if not host:
        raise SystemExit("Set OS_HOST (and optionally OS_USER/OS_PASS).")
    user, pwd = os.getenv("OS_USER"), os.getenv("OS_PASS")
    return OpenSearch(hosts=[host],
                      http_auth=(user, pwd) if user and pwd else None,
                      timeout=90,
                      max_retries=3,
                      retry_on_timeout=True,
                      verify_certs=False,
                      ssl_show_warn=False)


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

    print(f"[SEED] Prices {tickers} {start_date}..{end_date}")
    fetch_prices.fetch_prices(tickers, start_date, end_date, output_file=prices_out)
    print(f"[INDEX] {prices_out} -> {DEFAULT_PRICES_INDEX}")
    helpers.bulk(client, actions_from_ndjson(prices_out), index=DEFAULT_PRICES_INDEX)

    print(f"[SEED] Earnings {tickers} {start_date}..{end_date}")
    if not polygon_api_key:
        polygon_api_key = os.getenv("POLYGON_API_KEY", "")
    if not polygon_api_key:
        raise SystemExit("Missing Polygon API key (set POLYGON_API_KEY or pass --api-key).")
    fetch_earnings.fetch_earnings(tickers, start_date, end_date, polygon_api_key, earnings_out)
    print(f"[INDEX] {earnings_out} -> {DEFAULT_EARNINGS_INDEX}")
    helpers.bulk(client, actions_from_ndjson(earnings_out), index=DEFAULT_EARNINGS_INDEX)

    if run_summary:
        print("[SUMMARY] update_stock_summary.py …")
        os.system(f"{sys.executable} update_stock_summary.py")


def load_tickers(arg: str) -> str:
    if os.path.isfile(arg):
        with open(arg) as f:
            syms = [ln.strip().upper() for ln in f if ln.strip()]
        return ",".join(syms)
    return ",".join(t.strip().upper() for t in arg.split(",") if t.strip())        


def parse_args():
    p = argparse.ArgumentParser(description="Seed new tickers with historical prices & earnings.")
    p.add_argument("tickers", help="Comma-separated tickers or path to a text file with one ticker per line.")
    p.add_argument("start_date", help="YYYY-MM-DD (historical start)")
    p.add_argument("end_date", help="YYYY-MM-DD (historical end)")
    p.add_argument("--api-key", default=os.getenv("POLYGON_API_KEY", ""))
    p.add_argument("--skip-summary", action="store_true")
    return p.parse_args()


def main():
    a = parse_args()
    tickers_csv = load_tickers(a.tickers)
    seed(tickers_csv, a.start_date, a.end_date, a.api_key, not a.skip_summary)

if __name__ == "__main__":
    main()
