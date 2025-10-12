#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys

from config import settings
from opensearchpy import OpenSearch, helpers
import fetch_earnings

DEFAULT_INDEX = "earnings_data"
DEFAULT_OUTPUT = "earnings.ndjson"
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


from typing import Any, Dict, List, Optional


def latest_dates(
    client,
    tickers: List[str],
    *,
    index: str = "earnings_data",
    ticker_field: str = "ticker",
    date_field: str = "filing_date",
    page_size: int = 1000,
) -> List[Dict[str, Optional[str]]]:
    """
    For each ticker, return its latest (max) {date_field} found in the index.

    Returns:
      [ {"ticker": "AAPL", "date": "2022-01-01"},
        {"ticker": "NKE",  "date": "2024-01-01"} ]

    Tickers with no docs are **omitted** from the result.
    """
    # Normalize input
    if not tickers:
        return []
    tickers = [t.strip() for t in tickers if t and t.strip()]

    # Composite aggregation over provided tickers to get max(date_field) per ticker
    after_key = None
    latest_per_ticker: Dict[str, Optional[str]] = {}

    while True:
        body: Dict[str, Any] = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [{
                        "terms": {
                            ticker_field: tickers
                        }
                    }]
                }
            },
            "aggs": {
                "by_ticker": {
                    "composite": {
                        "size": page_size,
                        "sources": [{
                            "ticker": {
                                "terms": {
                                    "field": ticker_field
                                }
                            }
                        }],
                    },
                    "aggs": {
                        "last_seen": {
                            "max": {
                                "field": date_field
                            }
                        }
                    },
                }
            },
        }
        if after_key:
            body["aggs"]["by_ticker"]["composite"]["after"] = after_key

        resp = client.search(index=index, body=body)
        comp = resp["aggregations"]["by_ticker"]
        for b in comp["buckets"]:
            tkr = b["key"]["ticker"]
            v = b["last_seen"].get("value_as_string")
            latest_per_ticker[tkr] = v[:10] if v else None  # YYYY-MM-DD

        after_key = comp.get("after_key")
        if not after_key:
            break

    # Return only tickers that were found in OpenSearch (preserve input order)
    out: List[Dict[str, Optional[str]]] = []

    for t in tickers:
        if t in latest_per_ticker:
            out.append({"ticker": t, "date": latest_per_ticker[t]})

    return out


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
    p.add_argument("--api-key", default=settings.POLYGON_API_KEY.get_secret_value())
    p.add_argument("--run-summary", action="store_true", help="Run update_stock_summary.py after indexing")
    return p.parse_args()


def load_tickers(arg: str) -> str:
    if os.path.isfile(arg):
        with open(arg) as f:
            syms = [ln.strip().upper() for ln in f if ln.strip()]
        return ",".join(syms)
    return ",".join(t.strip().upper() for t in arg.split(",") if t.strip())


import re


def normalize_tickers(tickers):
    if isinstance(tickers, str):
        return [t for t in re.split(r"[,\s]+", tickers) if t]
    return list(tickers)


def main():
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing Polygon API key. Set POLYGON_API_KEY or pass --api-key.")

    client = os_client()
    tickers_csv = load_tickers(args.tickers)
    tickers_list = normalize_tickers(tickers_csv)

    end = args.end_date or dt.date.today().strftime("%Y-%m-%d")
    if args.start_date:
        tickers_with_dates = [{"ticker": t, "date": args.start_date} for t in tickers_list]
    else:
        tickers_with_dates = latest_dates(client, tickers_list)
        for tic in tickers_with_dates:
            tic["date"] = plus_one(tic["date"])

    for tic in tickers_with_dates:
        print(f"[EARNINGS] Fetch {tic['ticker']} {tic['date']}..{end}")

    fetch_earnings.fetch_earnings_with_different_start_date(tickers_with_dates, end, args.api_key, args.output)

    # Index to OpenSearch
    added = index_ndjson(client, args.index, args.output)
    print(f"[INDEX] Wrote {added} docs to '{args.index}'")

    if args.run_summary:
        arg = ",".join(tickers_list)
        os.system(f"{sys.executable} update_stock_summary.py {arg}")


if __name__ == "__main__":
    main()
