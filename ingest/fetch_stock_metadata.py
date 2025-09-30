
#!/usr/bin/env python3
"""Fetch stock metadata (sector, industry, etc.) from Polygon and write NDJSON.

Usage (CLI):
  python fetch_stock_metadata.py AAPL,MSFT,TSLA --api-key YOUR_KEY -o stock_metadata.json

Programmatic:
  from fetch_stock_metadata import fetch_stock_metadata
  fetch_stock_metadata("AAPL,MSFT", api_key="...", output_file="out.json")
"""
import argparse
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

import requests

DEFAULT_OUTPUT_FILE = "stock_metadata.json"


# ── SIC → Sector helpers ─────────────────────────────────────────────────────────
def _parse_sic(code: Optional[str]) -> Optional[int]:
    if code is None:
        return None
    try:
        return int(str(code)[:4])
    except Exception:
        return None


def _in(i: int, lo: int, hi: int) -> bool:
    return lo <= i <= hi


def derive_sector_from_sic(sic_code: Optional[str]) -> Optional[str]:
    """Heuristic mapping from 4‑digit SIC to a modern-ish sector.

    Notes:
    - Prefers your app's buckets: Technology, HealthCare, Finance, Energy, Utilities,
      Consumer, Industrial, Materials, Real Estate (last two optional but useful).
    - Uses coarse ranges with targeted overrides for common modern cases.
    - Returns None if it can't form a confident mapping.
    """
    i = _parse_sic(sic_code)
    if i is None:
        return None

    # --- Targeted overrides (frequent modern tickers) --------------------------
    # Core Tech manufacturing & services
    if _in(i, 3570, 3579):      # Computer & office equipment (e.g., 3571 Electronic Computers)
        return "Technology"
    if _in(i, 3660, 3699):      # Communications & electronic equipment
        return "Technology"
    if _in(i, 3670, 3679):      # Electronic components, semiconductors
        return "Technology"
    if _in(i, 7370, 7379):      # Computer programming, data processing, prepackaged software
        return "Technology"
    # Health care manufacturing & services
    if _in(i, 2830, 2839):      # Drugs
        return "HealthCare"
    if _in(i, 3840, 3851):      # Surgical, medical, dental instruments & supplies
        return "HealthCare"
    if _in(i, 8000, 8099):      # Health services
        return "HealthCare"
    # Utilities (power, gas, water, sanitary)
    if _in(i, 4910, 4999):
        return "Utilities"
    # Energy (oil & gas extraction, pipelines, coal)
    if _in(i, 1310, 1389) or _in(i, 2900, 2999):
        return "Energy"
    # Real Estate (REITs, operators)
    if _in(i, 6500, 6799):
        # Many apps split Real Estate; if you prefer Finance, change here.
        return "Real Estate"

    # --- Broad ranges fallback -------------------------------------------------
    if _in(i, 100, 999):    # 0100–0999 Agriculture, Forestry & Fishing
        return "Industrial"
    if _in(i, 1000, 1499):  # Mining
        return "Materials"
    if _in(i, 1500, 1799):  # Construction
        return "Industrial"
    if _in(i, 2000, 3999):  # Manufacturing (mixed bag)
        # If it wasn't caught by overrides, treat as Industrials/Consumer depending on subrange
        if _in(i, 2000, 2399) or _in(i, 2500, 2599) or _in(i, 3000, 3199):
            return "Consumer"
        return "Industrial"
    if _in(i, 4000, 4899):  # Transportation & Communications/Public Utilities
        # Transportation likely Industrial; (4910+ handled above as Utilities)
        return "Industrial"
    if _in(i, 5000, 5999):  # Wholesale & Retail Trade
        return "Consumer"
    if _in(i, 6000, 6499):  # Finance, Insurance (6500–6799 handled above)
        return "Finance"
    if _in(i, 7000, 7999):  # Services (very mixed)
        # Entertainment, recreation -> Consumer
        if _in(i, 7800, 7999):
            return "Consumer"
        return "Industrial"
    if _in(i, 9100, 9729):  # Public Administration
        return "Industrial"

    return None


# ── HTTP helpers (mirrors style of fetch_earnings.py) ─────────────────────────
def polygon_get(url: str, api_key: str, max_retries: int = 10, sleep_base: float = 2.0):
    """GET with basic retry & better error messages."""
    headers = {"Accept": "application/json"}
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp
        if resp.status_code == 401:
            msg = resp.text.strip()
            raise SystemExit(
                f"[ERROR] HTTP 401 from Polygon. Your API key is missing/invalid or lacks access.\n"
                f"URL: {url}\nResponse: {msg}\n"
                f"Tip: export POLYGON_API_KEY=... or use --api-key ..."
            )
        if resp.status_code == 429:
            wait = sleep_base * (2 ** attempt)
            print(f"[WARN] 429 rate-limited. Sleeping {wait}s and retrying...", file=sys.stderr)
            time.sleep(wait)
            continue
        wait = min(10, sleep_base * (attempt + 1))
        print(f"[WARN] HTTP {resp.status_code}. Sleeping {wait}s and retrying...", file=sys.stderr)
        time.sleep(wait)
    resp.raise_for_status()


def _with_key(u: str, key: str) -> str:
    if not u:
        return u
    return u if "apiKey=" in u else (u + ("&" if "?" in u else "?") + f"apiKey={key}")


# ── Polygon calls ─────────────────────────────────────────────────────────────
def fetch_ticker_metadata_once(ticker: str, api_key: str) -> Dict[str, Any]:
    """Fetch a single ticker's reference metadata from Polygon.

    Endpoint: /v3/reference/tickers/{ticker}
    """
    base = f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}"
    url = _with_key(base, api_key)
    resp = polygon_get(url, api_key)
    data = resp.json() or {}
    result = data.get("results") or {}
    return result


def _pluck_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten Polygon's results into a compact metadata doc, with sector fallback."""
    if not isinstance(result, dict):
        return {}
    sic_code = result.get("sic_code")
    sector = result.get("sector") or derive_sector_from_sic(sic_code)
    derived = {
        "ticker": result.get("ticker"),
        "name": result.get("name"),
        "market": result.get("market"),
        "locale": result.get("locale"),
        "primary_exchange": result.get("primary_exchange"),
        "type": result.get("type"),
        "active": result.get("active"),
        "currency_name": result.get("currency_name"),
        "share_class_shares_outstanding": result.get("share_class_shares_outstanding"),
        "weighted_shares_outstanding": result.get("weighted_shares_outstanding"),
        # Classifications
        "sic_code": sic_code,
        "sic_description": result.get("sic_description"),
        "sic_sector": result.get("sic_sector"),
        "sector": sector,
        "industry": result.get("industry"),
        # Web + misc
        "homepage_url": result.get("homepage_url"),
        "description": result.get("description"),
        # Provenance (helpful for debugging/refresh logic)
        "source": {
            "provider": "polygon",
            "as_of": result.get("updated_utc") or result.get("request_id"),
            "sector_derived_from_sic": bool(result.get("sector") is None and sector is not None),
        },
        "updated_utc": result.get("updated_utc"),
    }
    return derived


# ── NDJSON writer (bulk-friendly: index action + doc) ────────────────────────
def write_ndjson(docs: List[Dict[str, Any]], output_path: str):
    with open(output_path, "w", encoding="utf-8") as out:
        for rec in docs:
            tid = (rec.get("ticker") or "NA").upper()
            doc_id = tid  # stable id per ticker
            out.write(json.dumps({"index": {"_id": doc_id}}) + "\n")
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── Public API ───────────────────────────────────────────────────────────────
def fetch_stock_metadata(tickers_csv: str, api_key: str, output_file: str = DEFAULT_OUTPUT_FILE) -> List[Dict[str, Any]]:
    """Fetch metadata for comma-separated tickers and write NDJSON.

    Returns the list of flattened metadata dicts.
    """
    tickers = [t.strip().upper() for t in tickers_csv.split(",") if t.strip()]
    all_docs: List[Dict[str, Any]] = []
    for t in tickers:
        print(f"→ Fetching {t}...", end="", flush=True)
        res = fetch_ticker_metadata_once(t, api_key)
        doc = _pluck_fields(res)
        all_docs.append(doc)
        print(" done.")
        time.sleep(0.25)  # gentle pacing
    write_ndjson(all_docs, output_file)
    print(f"\nDone. Wrote {len(all_docs)} records to {output_file}")
    return all_docs


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Fetch Polygon reference metadata (sector, industry, etc.) for tickers.")
    p.add_argument("tickers", help="Comma-separated tickers, e.g. AAPL,MSFT,TSLA")
    p.add_argument("--api-key", default=os.getenv("POLYGON_API_KEY", ""), help="Polygon API key (or set env POLYGON_API_KEY)")
    p.add_argument("-o", "--output", default=DEFAULT_OUTPUT_FILE, help=f"Output NDJSON file (default: {DEFAULT_OUTPUT_FILE})")
    return p.parse_args()


def main():
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set env POLYGON_API_KEY or pass --api-key YOUR_KEY")
    fetch_stock_metadata(args.tickers, api_key=args.api_key, output_file=args.output)


if __name__ == "__main__":
    main()
