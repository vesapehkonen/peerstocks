#!/usr/bin/env python3
import os, sys, argparse, json, datetime as dt
from opensearchpy import OpenSearch, helpers

DEFAULT_INDEX = "earnings_data"
DEFAULT_OUTPUT = "earnings.ndjson"


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


def latest_date(client, index: str, date_field: str = "filing_date") -> str | None:
    if not client.indices.exists(index=index):
        return None
    body = {"size": 0, "aggs": {"max_date": {"max": {"field": date_field}}}}
    resp = client.search(index=index, body=body, request_timeout=60)
    val = resp.get("aggregations", {}).get("max_date", {}).get("value_as_string")
    return val[:10] if val else None


def plus_one(s: str) -> str:
    import datetime as dt
    d = dt.datetime.strptime(s, "%Y-%m-%d").date()
    return (d + dt.timedelta(days=1)).strftime("%Y-%m-%d")


def actions_from_ndjson(path: str):
    with open(path, "r") as f:
        while True:
            meta = f.readline()
            if not meta: break
            src = f.readline()
            if not src: break
            mo = json.loads(meta)
            op = next(iter(mo))
            _id = mo[op].get("_id")
            yield {"_op_type": "index", "_id": _id, "_source": json.loads(src)}


def index_ndjson(client, index: str, path: str) -> int:
    return helpers.bulk(client, actions_from_ndjson(path), index=index, request_timeout=120)[0]


def parse_args():
    p = argparse.ArgumentParser(description="Weekly earnings updater: detect missing range, fetch, index.")
    p.add_argument("tickers", help="Comma-separated tickers or path to a text file with one ticker per line.")
    p.add_argument("--index", default=DEFAULT_INDEX)
    p.add_argument("--start-date", help="YYYY-MM-DD (overrides auto-detected start)")
    p.add_argument("--end-date", help="YYYY-MM-DD (default: today)")
    p.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
    p.add_argument("--api-key", default=os.getenv("POLYGON_API_KEY", ""))
    p.add_argument("--run-summary", action="store_true", help="Run update_stock_summary.py after indexing")
    return p.parse_args()


def load_tickers(arg: str) -> str:
    if os.path.isfile(arg):
        with open(arg) as f:
            syms = [ln.strip().upper() for ln in f if ln.strip()]
        return ",".join(syms)
    return ",".join(t.strip().upper() for t in arg.split(",") if t.strip())


def main():
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing Polygon API key. Set POLYGON_API_KEY or pass --api-key.")

    client = os_client()

    # Determine date range
    end = args.end_date or dt.date.today().strftime("%Y-%m-%d")
    if args.start_date:
        start = args.start_date
    else:
        latest = latest_date(client, args.index, "filing_date")
        if latest:
            start = plus_one(latest)
        else:
            raise SystemExit("Index empty. Provide --start-date for initial backfill.")

    tickers_csv = load_tickers(args.tickers)
    print(f"[EARNINGS] {tickers_csv[:80]}{'...' if len(tickers_csv)>80 else ''} {start}..{end}")

    # Call your existing fetcher
    import fetch_earnings
    fetch_earnings.fetch_earnings(tickers_csv, start, end, args.api_key, args.output)

    # Index to OpenSearch
    added = index_ndjson(client, args.index, args.output)
    print(f"[INDEX] Wrote {added} docs to '{args.index}'")

    if args.run_summary:
        os.system(f"{sys.executable} update_stock_summary.py")


if __name__ == "__main__":
    main()
