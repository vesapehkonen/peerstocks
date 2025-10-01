#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

from config import settings
from fetch_prices import fetch_prices
from opensearchpy import OpenSearch, helpers

DEFAULT_INDEX = "stock_prices"
DEFAULT_OUTPUT = "prices.ndjson"
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


import re


def normalize_tickers(tickers):
    if isinstance(tickers, str):
        return [t for t in re.split(r"[,\s]+", tickers) if t]
    return list(tickers)


from typing import Any, Dict, List, Optional


def latest_dates(
    client,
    tickers: List[str],
    *,
    index: str = "stock_prices",
    ticker_field: str = "ticker",
    date_field: str = "date",
    page_size: int = 1000
) -> List[Dict[str, Any]]:

    print(tickers)
    """
    Return a list of { 'date': <YYYY-MM-DD or None>, 'tickers': [ ... ] } buckets,
    where each bucket groups the provided tickers by their latest (max) date found
    in the index. Tickers with no documents are grouped under date=None.

    Example:
    [
      {"date": "2024-01-01", "tickers": ["GOOG", "AAPL"]},
      {"date": None, "tickers": ["MISSING1"]}
    ]
    """
    if not tickers:
        return []

    # Aggregate latest date per ticker (restricted to provided tickers)
    buckets_map: Dict[Optional[str], List[str]] = {}
    after_key = None

    while True:
        body = {
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
            # value_as_string is ISO datetime; we only need YYYY-MM-DD
            v = b["last_seen"].get("value_as_string")
            date_key: Optional[str] = v[:10] if v else None
            buckets_map.setdefault(date_key, []).append(tkr)

        after_key = comp.get("after_key")
        if not after_key:
            break

    # Ensure every requested ticker appears (missing tickers => date=None)
    seen = {t for lst in buckets_map.values() for t in lst}
    for t in tickers:
        if t not in seen:
            buckets_map.setdefault(None, []).append(t)

    # Build sorted list of {date, tickers}; put None last; sort tickers for determinism
    dates = [d for d in buckets_map.keys() if d is not None]
    dates.sort(reverse=True)  # newest first

    # Returns comma separated list of tickers
    def format_tickers(ts: List[str]):
        ts = sorted(ts)
        return ",".join(ts)

    result: List[Dict[str, Any]] = [{"date": d, "tickers": format_tickers(buckets_map[d])} for d in dates]
    if None in buckets_map:
        result.append({"date": None, "tickers": format_tickers(buckets_map[None])})

    # Returns list of tickers
    #result: List[Dict[str, Any]] = [{"date": d, "tickers": sorted(buckets_map[d])} for d in dates]
    #if None in buckets_map:
    #    result.append({"date": None, "tickers": sorted(buckets_map[None])})

    return result


def latest_date(client, index: str, date_field: str = "date") -> str | None:
    if not client.indices.exists(index=index):
        return None

    body = {"size": 0, "query": {"term": {"ticker": ticker}}, "aggs": {"max_date": {"max": {"field": "date_field"}}}}
    resp = client.search(index=index, body=body, request_timeout=60)
    val = resp.get("aggregations", {}).get("max_date", {}).get("value_as_string")
    return val[:10] if val else None


def plus_one(s: str) -> str:
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
    p = argparse.ArgumentParser(description="Daily prices updater: detect missing range, fetch, index.")
    p.add_argument("tickers", help="Comma-separated tickers or path to a text file with one ticker per line.")
    p.add_argument("--index", default=DEFAULT_INDEX)
    p.add_argument("--start-date", help="YYYY-MM-DD (overrides auto-detected start)")
    p.add_argument("--end-date", help="YYYY-MM-DD (default: today)")
    p.add_argument("-o", "--output", default=DEFAULT_OUTPUT)
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
    client = os_client()

    tickers_csv = load_tickers(args.tickers)
    tickers_list = normalize_tickers(tickers_csv)

    # Determine date range
    end_date = dt.date.fromisoformat(args.end_date) if args.end_date else dt.date.today()

    if args.start_date:
        buckets = [{"date": args.start_date, "tickers": tickers_list}]
    else:
        buckets = latest_dates(client, tickers_list)

    for bucket in buckets:
        start_date_str = bucket["date"]
        if start_date_str:
            # parse and advance one day to avoid re-fetching the last indexed date
            start_date = dt.date.fromisoformat(start_date_str) + dt.timedelta(days=1)
            tickers = bucket["tickers"]
            print(
                f"[PRICES] {tickers[:80]}{'...' if len(tickers)>80 else ''} {start_date.isoformat()}..{end_date.isoformat()}"
            )
            if start_date <= dt.date.today() and start_date <= end_date:
                fetch_prices(tickers, start_date.isoformat(), end_date.isoformat(), output_file=args.output)
                added = index_ndjson(client, args.index, args.output)
                print(f"[INDEX] Wrote {added} docs to '{args.index}'")

    if args.run_summary:
        os.system(f"{sys.executable} update_stock_summary.py {tickers_list}")


if __name__ == "__main__":
    main()
