import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict
import sys
from pathlib import Path

from config import settings
from opensearchpy import OpenSearch

CONNECT_TIMEOUT = 3
REQUEST_TIMEOUT = 20


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


_CLIENT = os_client()

def fetch_sector_map() -> Dict[str, str]:
    """
    Load sectors for all tickers from stock_metadata.
    Prefers _source['ticker'] and falls back to _id as the key.
    """
    query = {
        "size": 10000,
        "_source": ["ticker", "sector"],
        "query": {"match_all": {}},
        "sort": [{"_id": "asc"}],
    }
    try:
        resp = _search("stock_metadata", query)
        hits = resp.get("hits", {}).get("hits", [])
        sector_map: Dict[str, str] = {}
        for h in hits:
            src = h.get("_source", {}) or {}
            key = (src.get("ticker") or h.get("_id") or "").upper()
            if key: sector_map[key] = src.get("sector")
        return sector_map
    except Exception:
        return {}


# Small helpers to match prior behavior
def _search(index: str, body: dict) -> dict:
    return _CLIENT.search(index=index, body=body, request_timeout=REQUEST_TIMEOUT)


def _index(index: str, doc_id: str, body: dict):
    # Use client.index, but preserve your printed status semantics:
    # 201 if created, 200 if updated; print non-2xx with error text.
    try:
        resp = _CLIENT.index(index=index, id=doc_id, body=body, request_timeout=REQUEST_TIMEOUT)
        result = (resp or {}).get("result")
        status = 201 if result == "created" else 200
        print(f"Indexed {doc_id}: {status}")
    except Exception as e:
        status = getattr(e, "status_code", 500)
        info = getattr(e, "info", str(e))
        msg = json.dumps(info)[:200] if isinstance(info, dict) else str(info)[:200]
        print(f"Indexed {doc_id}: {status} {msg}")


def fetch_all_tickers():
    aggs_query = {
        "size": 0,
        "aggs": {
            "unique_tickers": {
                "terms": {
                    "field": "ticker",
                    "size": 10000
                }
            }
        },
    }
    resp = _search("earnings_data", aggs_query)
    buckets = resp.get("aggregations", {}).get("unique_tickers", {}).get("buckets", [])
    return [b.get("key") for b in buckets if "key" in b]


def fetch_prices(ticker):
    query = {
        "size": 5000,
        "query": {
            "term": {
                "ticker": ticker
            }
        },
        "sort": [{
            "date": "asc"
        }],
    }
    resp = _search("stock_prices", query)
    hits = resp.get("hits", {}).get("hits", [])
    return [(h.get("_source", {}).get("date"), h.get("_source", {}).get("close")) for h in hits if h.get("_source")]


def fetch_earnings(ticker):
    query = {
        "size": 500,
        "query": {
            "term": {
                "ticker": ticker
            }
        },
        "sort": [{
            "filing_date": "desc"
        }],
    }
    resp = _search("earnings_data", query)
    return resp.get("hits", {}).get("hits", [])


def calc_cagr(start, end, years):
    if start <= 0 or end <= 0 or years <= 0:
        return None
    try:
        return round((end / start)**(1 / years) - 1, 4) * 100
    except:
        return None


def compute_ttm_eps(earnings):
    sorted_eps = [
        doc["_source"]["basic_eps"]
        for doc in sorted(earnings, key=lambda x: x["_source"]["end_date"], reverse=True)
        if isinstance(doc["_source"].get("basic_eps"), (int, float))
    ]
    if len(sorted_eps) >= 4:
        return round(sum(sorted_eps[:4]), 2)
    return None


def get_latest_price(price_data):
    if not price_data:
        return None
    return price_data[-1][1]


def find_price_years_ago(price_data, years):
    if not price_data:
        return None
    last_date = datetime.strptime(price_data[-1][0], "%Y-%m-%d")
    cutoff = last_date.replace(year=last_date.year - years)
    for date_str, price in reversed(price_data):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date <= cutoff:
            return price
    return None


def find_quarter_revenue(earnings, year, period):
    for doc in earnings:
        fy = doc["_source"].get("fiscal_year")
        fp = doc["_source"].get("fiscal_period", "").upper()
        rev = doc["_source"].get("revenues")
        if fy == str(year) and fp == period and isinstance(rev, (int, float)):
            return rev
    return None


def find_revenue_growth_cagr(earnings, years):
    period_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}
    sorted_docs = sorted(
        earnings,
        key=lambda d: (
            d["_source"].get("fiscal_year", 0),
            period_order.get(d["_source"].get("fiscal_period", "").upper(), 0),
        ),
    )
    for doc in reversed(sorted_docs):
        fy = doc["_source"].get("fiscal_year")
        fp = doc["_source"].get("fiscal_period", "").upper()
        rev_now = doc["_source"].get("revenues")
        if isinstance(rev_now, (int, float)) and fp in {"Q1", "Q2", "Q3", "Q4", "FY"}:
            rev_then = find_quarter_revenue(earnings, int(fy) - years, fp)
            if rev_then:
                return calc_cagr(rev_then, rev_now, years)
            break
    return None


def get_price_trend_5y(ticker: str) -> list[float]:
    end = datetime.today()
    start = end.replace(year=end.year - 5)

    query = {
        "size": 5000,
        "query": {
            "bool": {
                "must": [
                    {
                        "term": {
                            "ticker": ticker
                        }
                    },
                    {
                        "range": {
                            "date": {
                                "gte": start.strftime("%Y-%m-%d"),
                                "lte": end.strftime("%Y-%m-%d")
                            }
                        }
                    },
                ]
            }
        },
        "sort": [{
            "date": "asc"
        }],
    }

    resp = _search("stock_prices", query)
    hits = resp.get("hits", {}).get("hits", [])

    prices_by_date = {
        h["_source"]["date"]: h["_source"]["close"]
        for h in hits
        if isinstance(h["_source"].get("close"), (int, float))
    }

    trend = []
    for y in range(start.year, end.year + 1):
        for m in [3, 6, 9, 12]:
            try:
                d = datetime(y, m, 31)
                while d.strftime("%Y-%m-%d") not in prices_by_date and d.day > 25:
                    d -= timedelta(days=1)
                trend.append(prices_by_date.get(d.strftime("%Y-%m-%d")))
            except:
                trend.append(None)

    return [p for p in trend if p is not None]


def get_last_n_annual_revenues(earnings: list, n: int = 5):

    revenues_by_year = defaultdict(dict)

    for doc in earnings:
        src = doc["_source"]
        year = src.get("fiscal_year")
        period = src.get("fiscal_period", "").upper()
        revenue = src.get("revenues")
        if isinstance(revenue, (int, float)):
            revenues_by_year[year][period] = revenue

    full_years = []

    for year in sorted(revenues_by_year.keys(), reverse=True):
        periods = revenues_by_year[year]
        has = lambda p: p in periods

        if has("FY"):
            full_years.append((year, periods["FY"], False))
        elif has("Q1") and has("Q2") and has("Q3"):
            avg_q = (periods["Q1"] + periods["Q2"] + periods["Q3"]) / 3
            est_fy = periods["Q1"] + periods["Q2"] + periods["Q3"] + avg_q
            full_years.append((year, round(est_fy, 2), True))
        elif has("Q1") and has("Q2"):
            avg_q = (periods["Q1"] + periods["Q2"]) / 2
            est_fy = periods["Q1"] + periods["Q2"] + avg_q * 2
            full_years.append((year, round(est_fy, 2), True))
        elif has("Q1"):
            est_fy = periods["Q1"] * 4
            full_years.append((year, round(est_fy, 2), True))
        else:
            continue

    full_years.sort()
    hist = full_years[-n:]
    res = []
    for (y, r, est) in hist:
        d = {"year": y, "revenue": r, "estimated": est}
        res.append(d)
    return res


def compute_financial_ratios(latest_earnings: dict, latest_price: float | None = None) -> dict:
    """
    Compute ROA, ROE, and Debt-to-Equity from a single earnings document (_source).
    Returns a dict of computed ratios.
    """
    src = latest_earnings.get("_source", {})
    assets = src.get("assets")
    equity = src.get("equity")
    liabilities = src.get("liabilities")
    net_income = src.get("net_income")
    shares = src.get("diluted_average_shares") or src.get("basic_average_shares")

    ratios = {}
    if isinstance(net_income, (int, float)) and isinstance(assets, (int, float)) and assets > 0:
        ratios["roa"] = round(net_income / assets * 100, 2)
    if isinstance(net_income, (int, float)) and isinstance(equity, (int, float)) and equity > 0:
        ratios["roe"] = round(net_income / equity * 100, 2)
    if isinstance(liabilities, (int, float)) and isinstance(equity, (int, float)) and equity > 0:
        ratios["debt_to_equity"] = round(liabilities / equity, 2)
    if latest_price and isinstance(shares, (int, float)) and shares > 0:
        ratios["market_cap"] = round(latest_price * shares, 2)

    return ratios


def index_summary_doc(ticker, doc):
    _index("stock_summary", ticker, {"ticker": ticker, **doc})


def parse_tickers_arg(arg: str) -> list[str]:
    """
    Accept either a comma-separated string like "AAPL,NKE,AMZN"
    or a file path with one ticker per line. Returns upper-cased tickers.
    """
    if "," in arg:
        return [t.strip().upper() for t in arg.split(",") if t.strip()]
    p = Path(arg)
    if p.exists() and p.is_file():
        return [line.strip().upper() for line in p.read_text().splitlines() if line.strip()]
    return [arg.strip().upper()] if arg.strip() else []


def update(tickers: list[str] | None = None):
    if tickers is None:
        tickers = fetch_all_tickers()
        print(f"Found {len(tickers)} tickers")
    else:
        print(f"Using {len(tickers)} tickers from argument")

    # Load sectors once per run (slow-changing metadata)
    sector_map = fetch_sector_map()
    print(f"Loaded sectors for {len(sector_map)} tickers from stock_metadata")

    for ticker in tickers:
        tkr_key = ticker.upper()
        prices = fetch_prices(ticker)
        earnings = fetch_earnings(ticker)

        if not prices or not earnings:
            continue

        doc = {}

        ttm_eps = compute_ttm_eps(earnings)
        latest = get_latest_price(prices)
        if ttm_eps and latest:
            doc["ttm_pe_ratio"] = round(latest / ttm_eps, 2)

        for years in [1, 3, 5]:
            past = find_price_years_ago(prices, years)
            if past and latest:
                doc[f"price_growth_{years}y"] = calc_cagr(past, latest, years)

        for years in [1, 3, 5]:
            growth = find_revenue_growth_cagr(earnings, years)
            if growth is not None:
                doc[f"revenue_growth_{years}y"] = growth

        doc["price_history"] = get_price_trend_5y(ticker)
        doc["revenue_history"] = get_last_n_annual_revenues(earnings)

        latest_earn = earnings[0]  # already sorted desc by filing_date
        ratios = compute_financial_ratios(latest_earn, get_latest_price(prices))
        doc.update(ratios)

        # Attach sector from stock_metadata (if available)
        sector = sector_map.get(tkr_key)
        if sector:
            doc["sector"] = sector

        if doc:
            index_summary_doc(ticker, doc)

def main():
    tickers = None
    if len(sys.argv) > 1 and sys.argv[1]:
        tickers = parse_tickers_arg(sys.argv[1])
    update(tickers)


if __name__ == "__main__":
    main()
