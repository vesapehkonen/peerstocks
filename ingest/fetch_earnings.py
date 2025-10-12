#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time

import requests

# ── Configuration ───────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_FILE = "earnings.json"
# ────────────────────────────────────────────────────────────────────────────────


def polygon_get(url, api_key, max_retries=10, sleep_base=8):
    """GET with basic retry & better error messages."""
    headers = {"Accept": "application/json"}
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp
        # Auth error: don't keep retrying
        if resp.status_code == 401:
            msg = resp.text.strip()
            raise SystemExit(
                f"[ERROR] HTTP 401 from Polygon. "
                f"Your API key is missing/invalid or lacks access.\n"
                f"URL: {url}\nResponse: {msg}\n"
                f"Tip: export POLYGON_API_KEY=... or use --api-key ..."
            )
        # Too many requests → backoff
        if resp.status_code == 429:
            wait = sleep_base * (2**attempt)
            print(f"[WARN] 429 rate-limited. Sleeping {wait}s and retrying...", file=sys.stderr)
            time.sleep(wait)
            continue
        # Other errors: brief backoff, then retry
        wait = min(10, sleep_base * (attempt + 1))
        print(f"[WARN] HTTP {resp.status_code}. Sleeping {wait}s and retrying...", file=sys.stderr)
        time.sleep(wait)
    # If we get here, give up
    resp.raise_for_status()


def _with_key(u: str, key: str) -> str:
    if not u:
        return u
    return u if "apiKey=" in u else (u + ("&" if "?" in u else "?") + f"apiKey={key}")


def fetch_earnings_range(ticker, start_date, end_date, api_key):
    base = (
        "https://api.polygon.io/vX/reference/financials"
        f"?ticker={ticker}"
        f"&filing_date.gte={start_date}"
        f"&filing_date.lte={end_date}"
        f"&limit=100"  # page size (tune per plan)
        f"&apiKey={api_key}"
    )
    url = _with_key(base, api_key)
    results = []

    while url:
        resp = polygon_get(url, api_key)
        data = resp.json() or {}
        batch = data.get("results", []) or []
        results.extend(batch)

        next_url = data.get("next_url")
        url = _with_key(next_url, api_key) if next_url else None
        # keep requests/minute modest; tune if your plan allows faster
        time.sleep(1.2)

    return results


def _safe_get(dct, path, default=None):
    """Safely traverse nested dicts using a list of keys."""
    cur = dct
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def process_earnings_data(results):
    """Turn each API result into a flat document dict."""
    docs = []
    for r in results:
        docs.append({
            "ticker": (r.get("tickers") or [None])[0],
            "company_name":
            r.get("company_name"),
            "fiscal_year":
            r.get("fiscal_year"),
            "fiscal_period":
            r.get("fiscal_period"),
            "filing_date":
            r.get("filing_date"),
            "start_date":
            r.get("start_date"),
            "end_date":
            r.get("end_date"),
            "revenues":
            _safe_get(r, ["financials", "income_statement", "revenues", "value"]),
            "operating_income":
            _safe_get(r, ["financials", "income_statement", "operating_income_loss", "value"]),
            "net_income":
            _safe_get(r, ["financials", "income_statement", "net_income_loss", "value"]),
            "basic_eps":
            _safe_get(r, ["financials", "income_statement", "basic_earnings_per_share", "value"]),
            "diluted_eps":
            _safe_get(r, ["financials", "income_statement", "diluted_earnings_per_share", "value"]),
            "assets":
            _safe_get(r, ["financials", "balance_sheet", "assets", "value"]),
            "liabilities":
            _safe_get(r, ["financials", "balance_sheet", "liabilities", "value"]),
            "equity":
            _safe_get(r, ["financials", "balance_sheet", "equity", "value"]),
            "cash_flow":
            _safe_get(r, ["financials", "cash_flow_statement", "net_cash_flow", "value"]),
            "basic_average_shares": _safe_get(r, ["financials", "income_statement", "basic_average_shares", "value"]),
            "diluted_average_shares": _safe_get(r, ["financials", "income_statement", "diluted_average_shares", "value"]),
        })
    return docs


def write_ndjson(docs, output_path):
    with open(output_path, "w") as out:
        for rec in docs:
            # Construct a stable id; fall back to filing_date if year/period missing
            fy = rec.get("fiscal_year") or "NA"
            fp = rec.get("fiscal_period") or (rec.get("filing_date") or "NA")
            tid = rec.get("ticker") or "NA"
            doc_id = f"{tid}_{fy}_{fp}"
            out.write(json.dumps({"index": {"_id": doc_id}}) + "\n")
            out.write(json.dumps(rec) + "\n")


def fetch_earnings(tickers_csv, start_date, end_date, api_key, output_file):
    tickers = [t.strip().upper() for t in tickers_csv.split(",") if t.strip()]
    all_docs = []

    for ticker in tickers:
        print(f"→ Fetching {ticker}...", end="", flush=True)
        results = fetch_earnings_range(ticker, start_date, end_date, api_key)
        docs = process_earnings_data(results)
        all_docs.extend(docs)
        print(f" {len(docs)} records")
        # Soft pacing between tickers
        time.sleep(1.0)

    write_ndjson(all_docs, output_file)
    print(f"\nDone. Wrote {len(all_docs)} records to {output_file}")


def fetch_earnings_with_different_start_date(tickers, end_date, api_key, output_file):
    all_docs = []

    for ticker in tickers:
        print(f"→ Fetching {ticker['ticker']}...", end="", flush=True)
        results = fetch_earnings_range(ticker["ticker"], ticker["date"], end_date, api_key)
        docs = process_earnings_data(results)
        all_docs.extend(docs)
        print(f" {len(docs)} records")
        # Soft pacing between tickers
        time.sleep(1.0)

    write_ndjson(all_docs, output_file)
    print(f"\nDone. Wrote {len(all_docs)} records to {output_file}")


def parse_args():
    p = argparse.ArgumentParser(description="Fetch Polygon financials between explicit start/end dates.")
    p.add_argument("tickers", help="Comma-separated tickers, e.g. AAPL,MSFT,TSLA")
    p.add_argument("start_date", help="Inclusive start date, YYYY-MM-DD")
    p.add_argument("end_date", help="Inclusive end date, YYYY-MM-DD")
    p.add_argument(
        "--api-key", default=os.getenv("POLYGON_API_KEY", ""), help="Polygon API key (or set env POLYGON_API_KEY)"
    )
    p.add_argument(
        "-o", "--output", default=DEFAULT_OUTPUT_FILE, help=f"Output NDJSON file (default: {DEFAULT_OUTPUT_FILE})"
    )
    return p.parse_args()


def main():
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set env POLYGON_API_KEY or pass --api-key YOUR_KEY")
    fetch_earnings(args.tickers, args.start_date, args.end_date, args.api_key, args.output)


if __name__ == "__main__":
    main()
