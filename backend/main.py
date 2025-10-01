from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import settings
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from opensearch_client import build_opensearch_client, run_opensearch_query, run_opensearch_raw
from pydantic import BaseModel
from stock_utils import fetch_earnings, find_existing_trading_day

app = FastAPI()

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
os_client = build_opensearch_client()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


class AdvancedSearchParams(BaseModel):
    peMax: Optional[float] = None
    priceGrowth: Optional[float] = None
    revenueGrowth1y: Optional[float] = None
    revenueGrowth3y: Optional[float] = None
    revenueGrowth5y: Optional[float] = None
    stockType: List[str] = []
    sector: List[str] = []


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/ai-summary_NW/{ticker}")
def generate_stock_summary_NEW(ticker: str):
    if not settings.OPENAI_API_KEY:
        return {"summary": "AI summary is disabled on this server."}

    tkr = ticker.upper()

    # --- Gather context ---
    earnings = fetch_earnings(tkr) or []
    # You implement these: use a news/market API (e.g., Finnhub, Polygon, Alpha Vantage, Yahoo)
    price = fetch_price_window(tkr, window_days=5)         # {change_pct, volume_vs_avg, sector_move_pct, teny_bps, notes}
    news = fetch_top_news(tkr, limit=5)                    # [{"id":"n1","date":"YYYY-MM-DD","headline":"..","summary":"..","link":".."}]
    actions = fetch_analyst_actions(tkr, days=14)          # [{"id":"a1","date":"..","action":"downgrade","broker":"..","pt_change":"-10%"}]

    # format last 4 earnings
    last4 = []
    for doc in earnings[-4:]:
        src = doc["_source"]
        last4.append({
            "period": src.get("end_date","N/A"),
            "revenue": src.get("revenues","N/A"),
            "eps": src.get("diluted_eps","N/A"),
            "gm": src.get("gross_margin_pct","N/A"),
            "notes": src.get("notes","")
        })

    context = {
        "as_of": datetime.date.today().isoformat(),
        "ticker": tkr,
        "window": "5D",
        "price_action": price,
        "earnings_trend": last4,
        "news": news,
        "analyst_actions": actions
    }

    system_prompt = (
        "You are a markets analyst. Explain WHY the stock moved or earnings trend changed, "
        "based ONLY on the provided context. Rank the strongest drivers first and tie each to a mechanism. "
        "State uncertainty if evidence is thin. Then give an up/down/neutral view for SHORT term (days–weeks) "
        "and LONG term (12+ months) with 1–2 reasons each. Not investment advice. "
        "HARD LIMIT: Max 500 characters. No bullets. No newlines."
    )

    user_prompt = f"<CONTEXT>\n{json.dumps(context, ensure_ascii=False)}\n</CONTEXT>\n" \
                  "Return a single paragraph under 500 characters."

    try:
        resp = openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "").strip()

        # Enforce the 500-character cap (letters limit) and strip newlines
        text = " ".join(text.split())
        if len(text) > 500:
            text = text[:497].rstrip() + "…"

        return {"summary": text or "No AI summary available right now."}
    except Exception as e:
        return {"summary": f"Failed to generate summary: {e}"}


@app.get("/api/ai-summary/{ticker}")
def generate_stock_summary(ticker: str):

    prompt = (
        f"You are a market analyst. Ticker is {ticker}. Use common, simple language. "
        "Explain WHY the stock moved or earnings trend changed. "
        "Then give an up/down/neutral view for SHORT term (days–weeks) and LONG term (12+ months). "
        "HARD LIMIT: 500 characters MAX. "
        "OUTPUT RULES:"
        "- Plain text, one paragraph, ≤500 characters."
        "- Write at a 9th grade reading level."
        "- Use simple English words only."
        "- No technical terms, no buzzwords, no slang."
        "- Expand or explain any required acronyms."
        "- Avoid long sentences or complex grammar."
        "- plain text only, no images, charts, tables, bullet points, or code blocks. "
        "Also say if it’s a good buy now."
    )
    
    try:
        response = openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL, messages=[{
                "role": "user",
                "content": prompt
            }], temperature=1
        )

        full_summary = (response.choices[0].message.content or "").strip()
        if not full_summary:
            return {"summary": "No AI summary available right now."}

        # Optional fallback post-trim
        #if full_summary.count(".") > 4 or len(full_summary.split()) > 120:
        #    short_prompt = f"Rewrite this to 100 words or less:\n\n{full_summary}"
        #    retry = openai_client.chat.completions.create(
        #        model=settings.OPENAI_MODEL, messages=[{
        #            "role": "user",
        #            "content": short_prompt
        #        }], temperature=1
        #    )
        #    return {"summary": retry.choices[0].message.content.strip()}

        return {"summary": full_summary}

    except Exception as e:
        return {"summary": f"Failed to generate summary: {str(e)}"}


@app.get("/api/price_history/{ticker}")
def get_price_history(ticker: str):
    query = {
        "size": 5000,
        "query": {
            "bool": {
                "must": [{
                    "term": {
                        "ticker": ticker.upper()
                    }
                }]
            }
        },
        "sort": [{
            "date": "asc"
        }]
    }
    data = run_opensearch_query(os_client, "stock_prices", query)
    return [{"date": doc["_source"]["date"], "price": doc["_source"]["close"]} for doc in data]


def resolve_identifier_to_ticker(identifier: str) -> str:
    """
    Resolve input which may be a ticker (e.g., AAPL) or a company name (e.g., Apple Inc.)
    to a single ticker using the stock_metadata index.
    - Exact ticker term match first
    - Then search by name (full or partial)
    - If ambiguous, raise 409 with candidate list
    """
    s = (identifier or "").strip()
    if not s:
        raise HTTPException(400, "Empty ticker or company name.")

    # 1) Exact ticker match
    exact = run_opensearch_query(os_client, "stock_metadata", {
        "size": 1,
        "query": {"term": {"ticker": s.upper()}}
    })
    if exact:
        return exact[0]["_source"]["ticker"]

    # 2) Company name search
    name_hits = run_opensearch_query(os_client, "stock_metadata", {
        "size": 5,
        "_source": ["ticker", "name", "active"],
        "query": {
            "bool": {
                "should": [
                    {"match_phrase": {"name": {"query": s}}},
                    {"match": {"name": {"query": s, "operator": "and"}}},
                    {"match_phrase_prefix": {"name": {"query": s}}}
                ],
                "minimum_should_match": 1
            }
        }
    })
    if not name_hits:
        raise HTTPException(404, f"No ticker or company named '{s}' found.")

    # Prefer exact case-insensitive name match if unique
    exact_name = [h for h in name_hits if (h.get("_source", {}).get("name") or "").lower() == s.lower()]
    if len(exact_name) == 1:
        return exact_name[0]["_source"]["ticker"]

    # Prefer a single active match if that disambiguates
    active_only = [h for h in name_hits if h.get("_source", {}).get("active") is True]
    if len(active_only) == 1:
        return active_only[0]["_source"]["ticker"]

    # Ambiguous: cannot return two tickers' data
    options = ", ".join(f"{h['_source'].get('ticker')} ({h['_source'].get('name')})" for h in name_hits)
    raise HTTPException(409, f"Ambiguous company name '{s}'. Candidates: {options}. Please specify a ticker symbol.")


@app.get("/api/stocks/{ticker}")
def get_stock_data(ticker: str):
    # Accept ticker code or company name
    resolved = resolve_identifier_to_ticker(ticker)
    docs = fetch_earnings(resolved.upper())

    quarters = {}
    for doc in docs:
        src = doc["_source"]
        key = f"{src['fiscal_year']}_{src['fiscal_period']}"
        quarters[key] = src

    result = []

    for year in range(2020, 2026):
        q_data = []
        for q in ["Q1", "Q2", "Q3"]:
            key = f"{year}_{q}"
            if key in quarters:
                src = quarters[key]
                end = src["end_date"]
                eps = src["diluted_eps"]
                price = find_existing_trading_day(src["ticker"], end)
                result.append({"quarter": f"{year} {q}", "date": end, "eps": eps, "price": price})
                q_data.append(eps)

        fy_key = f"{year}_FY"
        if fy_key in quarters and len(q_data) == 3:
            fy = quarters[fy_key]
            eps_q4 = round(fy["diluted_eps"] - sum(q_data), 2)
            end = fy["end_date"]
            price = find_existing_trading_day(fy["ticker"], end)
            result.append({"quarter": f"{year} Q4", "date": end, "eps": eps_q4, "price": price})

    for i in range(len(result)):
        if i >= 3:
            ttm_eps = round(sum(result[j]["eps"] for j in range(i - 3, i + 1)), 2)
            price = result[i]["price"]
            pe = round(price / ttm_eps, 2) if isinstance(price, (float, int)) and ttm_eps else None
        else:
            ttm_eps, pe = None, None
        result[i]["ttm_eps"] = ttm_eps
        result[i]["pe_ratio"] = pe

    # Add daily prices for charting
    price_query = {
        "size": 5000,
        "query": {
            "bool": {
                "must": [{
                    "term": {
                        "ticker": resolved.upper()
                    }
                }]
            }
        },
        "sort": [{
            "date": "asc"
        }]
    }

    # Fetch metadata from stock_metadata
    meta_query = {
        "size": 1,
        "query": {"term": {"ticker": resolved.upper()}}
    }
    meta_data = run_opensearch_query(os_client, "stock_metadata", meta_query)
    metadata = meta_data[0]["_source"] if meta_data else {}
    
    price_data = run_opensearch_query(os_client, "stock_prices", price_query)
    daily_prices = [{"date": doc["_source"]["date"], "price": doc["_source"]["close"]} for doc in price_data]
    print(f"Returned: quarterly.lenght: {len(result)} daily_prices.length: {len(daily_prices)}")

    #resp = {"metadata": metadata, "quarterly": result, "daily_prices": daily_prices}
    #import json
    #print(json.dumps(metadata, indent=2))
    #print(json.dumps(resp, indent=2))

    return {"metadata": metadata, "quarterly": result, "daily_prices": daily_prices}


from typing import List


def eps_ttm_points(ticker: str, max_years: int = 6) -> List[Dict[str, Any]]:
    """
    Returns points [{date:'YYYY-MM-DD', eps_ttm: float}] at each reported quarter end.
    - Uses diluted EPS when available, else basic.
    - Derives Q4 as FY - (Q1 + Q2 + Q3) when no Q4 rows exist.
    - Computes TTM as the rolling sum of the last 4 quarters.
    """

    def choose_eps(src):
        x = src.get("diluted_eps")
        if x is None:
            x = src.get("basic_eps")
        return None if x is None else float(x)

    since = (datetime.now(timezone.utc) - timedelta(days=365 * max_years)).date().isoformat()

    hits = run_opensearch_query(
        os_client, "earnings_data", {
            "size": 2000,
            "sort": [{
                "end_date": {
                    "order": "asc"
                }
            }],
            "_source": ["fiscal_year", "fiscal_period", "end_date", "diluted_eps", "basic_eps", "ticker"],
            "query": {
                "bool": {
                    "filter": [{
                        "term": {
                            "ticker": ticker
                        }
                    }, {
                        "range": {
                            "end_date": {
                                "gte": since
                            }
                        }
                    }]
                }
            },
        }
    )

    # Collect by (year, period)
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for h in hits:
        s = h["_source"]
        key = (int(s["fiscal_year"]), s["fiscal_period"])  # e.g., (2023, "Q2") or (2023, "FY")
        by_key[key] = s  # last one wins if duplicates

    # Build a clean quarterly stream using reported Q1..Q3 and derived Q4 from FY
    quarters: List[Dict[str, Any]] = []
    years = sorted({y for (y, _) in by_key.keys()})
    for y in years:
        # Q1..Q3 if present
        q_vals = []
        for p in ("Q1", "Q2", "Q3"):
            s = by_key.get((y, p))
            if not s:
                continue
            eps = choose_eps(s)
            if eps is None:
                continue
            quarters.append({
                "date": s["end_date"][:10],
                "eps": eps,
            })
            q_vals.append(eps)

        # Q4 derived from FY (only if we have Q1..Q3 and FY exists)
        if len(q_vals) == 3:
            fy = by_key.get((y, "FY"))
            if fy:
                fy_eps = choose_eps(fy)
                if fy_eps is not None:
                    q4_eps = fy_eps - sum(q_vals)  # no rounding here
                    quarters.append({
                        "date": fy["end_date"][:10],  # use FY end as Q4 end
                        "eps": q4_eps,
                    })

    # Strict chronological order
    quarters.sort(key=lambda r: r["date"])

    # Rolling sum of last 4 quarters → TTM EPS
    out: List[Dict[str, Any]] = []
    window: List[float] = []
    total = 0.0
    for q in quarters:
        window.append(q["eps"])
        total += q["eps"]
        if len(window) > 4:
            total -= window.pop(0)
        if len(window) == 4:
            # round only at output
            out.append({"date": q["date"], "eps_ttm": round(total, 2)})

    return out


def prices_last_days_with_eps_pe(ticker: str, days: int) -> List[Dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    query = {
        "size": 2000,
        "track_total_hits": False,
        "sort": [{
            "date": {
                "order": "asc"
            }
        }],
        "_source": ["date", "close"],
        "query": {
            "bool": {
                "filter": [{
                    "term": {
                        "ticker": ticker
                    }
                }, {
                    "range": {
                        "date": {
                            "gte": since
                        }
                    }
                }]
            }
        },
    }
    price_hits = run_opensearch_query(os_client, "stock_prices", query)
    prices = [{"date": h["_source"]["date"][:10], "close": h["_source"]["close"]} for h in price_hits]

    # quarterly EPS TTM points
    eps_points = eps_ttm_points(ticker)

    p_idx = 0
    for eps in eps_points:
        d = eps["date"]
        while p_idx < len(prices) and prices[p_idx]["date"] < d:
            p_idx += 1
        if p_idx < len(prices):
            prices[p_idx]["eps"] = eps["eps_ttm"]
            prices[p_idx]["pe"] = prices[p_idx]["close"] / eps["eps_ttm"]
    """
    # forward-fill EPS TTM to each price date (last known EPS_TTM at or before date)
    eps_idx = 0
    for p in prices:
        d = p["date"]
        while eps_idx + 1 < len(eps_points) and eps_points[eps_idx + 1]["date"] <= d:
            eps_idx += 1
        eps_ttm = eps_points[eps_idx]["eps_ttm"] if eps_points and eps_points[eps_idx]["date"] <= d else None
        p["eps"] = eps_ttm
        p["pe"] = (p["close"] / eps_ttm) if eps_ttm not in (None, 0) else None
    """

    return prices


def latest_two_prices(ticker):
    query = {
        "size": 2,
        "sort": [{
            "date": {
                "order": "desc"
            }
        }],
        "_source": ["date", "close", "dividend_yield", "pe_ratio"],
        "query": {
            "term": {
                "ticker": ticker
            }
        },
    }
    hits = run_opensearch_query(os_client, "stock_prices", query)
    return [h["_source"] for h in hits] if hits else None


def prices_last_days(ticker, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    query = {
        "size": 2000,
        "sort": [{
            "date": {
                "order": "asc"
            }
        }],
        "_source": ["date", "close", "pe_ratio"],
        "query": {
            "bool": {
                "filter": [{
                    "term": {
                        "ticker": ticker
                    }
                }, {
                    "range": {
                        "date": {
                            "gte": since
                        }
                    }
                }]
            }
        }
    }
    hits = run_opensearch_query(os_client, "stock_prices", query)
    out = []
    for h in hits:
        src = h["_source"]
        out.append({
            "date": src["date"][:10],
            "close": src.get("close"),
            "pe": src.get("pe_ratio"),  # may be None for some days; frontend should skip/null
        })
    return out
    #return [{"date": h["_source"]["date"][:10], "close": h["_source"]["close"]} for h in hits]


def hi_lo_52w(ticker):
    since = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [{
                    "term": {
                        "ticker": ticker
                    }
                }, {
                    "range": {
                        "date": {
                            "gte": since
                        }
                    }
                }]
            }
        },
        "aggs": {
            "hi": {
                "max": {
                    "field": "close"
                }
            },
            "lo": {
                "min": {
                    "field": "close"
                }
            },
        },
    }
    resp = run_opensearch_raw(os_client, "stock_prices", query)
    agg = resp.get("aggregations", {})
    if not agg:
        return None
    return {"hi": agg["hi"]["value"], "lo": agg["lo"]["value"]}


def latest_summary_pe(ticker):
    query = {
        "size": 1,
        "sort": [{
            "ttm_pe_ratio": {
                "order": "desc"
            }
        }],  # any sort; we just want the doc if exists
        "_source": ["ttm_pe_ratio"],
        "query": {
            "term": {
                "ticker": ticker
            }
        },
    }
    hits = run_opensearch_query(os_client, "stock_summary", query)
    if not hits:
        return None
    return hits[0]["_source"].get("ttm_pe_ratio")


def latest_earnings(ticker):
    # newest by end_date
    query = {
        "size": 1,
        "sort": [{
            "end_date": {
                "order": "desc"
            }
        }],
        "_source": ["company_name", "revenues", "net_income", "operating_income", "cash_flow"],
        "query": {
            "term": {
                "ticker": ticker
            }
        },
    }
    hits = run_opensearch_query(os_client, "earnings_data", query)
    return hits[0]["_source"] if hits else None


def get_growns(ticker):
    query = {
        "_source": [
            "ticker", "ttm_pe_ratio", "price_growth_1y", "price_growth_3y", "price_growth_5y", "revenue_growth_1y",
            "revenue_growth_3y", "revenue_growth_5y"
        ],
        "query": {
            "terms": {
                "ticker": [ticker]
            }
        }
    }
    hits = run_opensearch_query(os_client, "stock_summary", query)
    return hits[0]["_source"] if hits else {}


def build_payload_for_ticker(ticker):
    t = ticker.upper()
    # prices
    two = latest_two_prices(t) or []
    last_close = two[0]["close"] if len(two) >= 1 else None
    prev_close = two[1]["close"] if len(two) >= 2 else None
    dividend_yield = two[0].get("dividend_yield") if len(two) >= 1 else None
    pe_latest = two[0].get("pe_ratio") if len(two) >= 1 else None

    # price change 1D
    change_pct_1d = None
    if last_close is not None and prev_close not in (None, 0):
        change_pct_1d = ((last_close / prev_close) - 1.0) * 100.0

    # 6 months of daily prices (~180 days)
    #series = prices_last_days(t, days=200)
    series = prices_last_days_with_eps_pe(t, days=2000)  # each point has {date, close, eps, pe}

    # 52w hi/lo
    hilo = hi_lo_52w(t) or {}
    hi, lo = hilo.get("hi"), hilo.get("lo")
    high52wPct = None
    low52wPct = None
    if last_close is not None and hi not in (None, 0):
        high52wPct = ((last_close / hi) - 1.0) * 100.0  # distance from high (negative if below)
    if last_close is not None and lo not in (None, 0):
        low52wPct = ((last_close / lo) - 1.0) * 100.0  # distance from low (positive if above)

    # ttm pe from summary if available
    ttm_pe = latest_summary_pe(t) or pe_latest

    # earnings snapshot
    earn = latest_earnings(t) or {}
    name = earn.get("company_name")
    revenues = earn.get("revenues")
    net_income = earn.get("net_income")
    operating_income = earn.get("operating_income")
    cash_flow = earn.get("cash_flow")

    # derived metrics
    net_margin = (net_income / revenues * 100.0) if revenues not in (None, 0) and net_income is not None else None
    operating_margin = (operating_income / revenues *
                        100.0) if revenues not in (None, 0) and operating_income is not None else None
    eps_ttm = (last_close / ttm_pe) if ttm_pe not in (None, 0) and last_close is not None else None

    growns = get_growns(t)

    return {
        "ticker": t,
        "name": name,
        "sector": None,  # not present in your indices
        "price": last_close,
        "changePct1D": change_pct_1d,
        #"pe": ttm_pe,
        #"epsTtm": eps_ttm,
        "marketCap": None,  # not present (no shares_outstanding)
        "divYield": dividend_yield,
        "beta": None,  # not present
        "high52wPct": high52wPct,
        "low52wPct": low52wPct,
        "grossMargin": None,  # not present; we expose operating & net instead
        "operatingMargin": operating_margin,
        "netMargin": net_margin,
        "freeCashFlowTtm": cash_flow,  # using earnings_data.cash_flow as a proxy
        "prices": series,  # [{date, close, eps, pe}]
        **growns
    }


@app.get("/api/stocks")
def get_stocks(tickers: List[str] = Query(..., description="Repeat param, e.g. ?tickers=AAPL&tickers=MSFT")):
    if not tickers:
        raise HTTPException(400, "No tickers provided")
    out: List[Dict[str, Any]] = []
    for t in tickers:
        out.append(build_payload_for_ticker(t.strip()))
    return out


@app.post("/api/advanced-search")
def advanced_search(params: AdvancedSearchParams = Body(...)):
    query = {
        "size": 100,
        "query": {
            "bool": {
                "must": [],
                "filter": [],
            }
        },
        "sort": [{
            "ticker": {
                "order": "asc"
            }
        }]
    }

    # Apply filters
    if params.peMax is not None:
        query["query"]["bool"]["must"].append({"range": {"ttm_pe_ratio": {"lte": params.peMax}}})

    if params.revenueGrowth5y is not None:
        query["query"]["bool"]["must"].append({"range": {"revenue_growth_5y": {"gte": params.revenueGrowth5y}}})

    if params.priceGrowth is not None:
        query["query"]["bool"]["must"].append({"range": {"price_growth_5y": {"gte": params.priceGrowth}}})

    if params.stockType:
        if len(params.stockType) > 0:
            query["query"]["bool"]["filter"].append({"terms": {"stock_type.keyword": params.stockType}})

    if params.sector:
        if len(params.sector) > 0:
            query["query"]["bool"]["filter"].append({"terms": {"sector.keyword": params.sector}})
    hits = run_opensearch_query(os_client, "stock_summary", query)
    return [hit["_source"] for hit in hits]
