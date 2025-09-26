#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from typing import Iterable, List, Union

import pandas as pd
import yfinance as yf

DEFAULT_OUTPUT_FILE = "prices.json"


def _as_list(tickers: Union[str, Iterable[str]]) -> List[str]:
    if isinstance(tickers, str):
        tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
    return tickers


def _safe_round(v, ndigits=2):
    try:
        if pd.isna(v):
            return None
        return round(float(v), ndigits)
    except Exception:
        return None


def _safe_int(v):
    try:
        if pd.isna(v):
            return 0
        return int(v)
    except Exception:
        return 0


def _download_prices_help(tickers, start_date, end_date) -> pd.DataFrame:
    # Make yfinance end inclusive by adding 1 day
    end_exclusive = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        df = yf.download(
            tickers,
            start=start_date,
            end=end_exclusive,
            interval="1d",
            auto_adjust=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        # Hard failure talking to Yahoo/network/etc.
        raise RuntimeError(f"Download failed for {tickers}: {e}") from e

    # If we got rows, return them
    if df is not None and not df.empty:
        return df

    # ---- Empty window: run a small probe to decide why ----
    try:
        probe = yf.download(
            tickers,
            period="5d",
            interval="1d",
            auto_adjust=False,
            group_by="ticker",
            threads=False,
            progress=False,
        )
    except Exception as e:
        raise RuntimeError(f"Probe failed for {tickers}: {e}") from e

    if probe is not None and not probe.empty:
        # Ticker/data source is fine → just no rows in requested window (weekend/holiday/too-early)
        return pd.DataFrame()

    # Still empty → treat as real failure (invalid ticker, outage, delisted, etc.)
    raise RuntimeError(f"No data returned for {tickers} in window and probe; treat as fetch_failed.")


def _download_prices(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Returns a normalized DataFrame with columns:
    ['date','ticker','Open','High','Low','Close','Adj Close','Volume']
    """

    df = _download_prices_help(tickers, start_date, end_date)
    if df.empty:
        print(f"[PRICES] No new data for {tickers} in [{start_date}..{end_date}]")
        return df

    # MULTI-TICKER CASE
    if isinstance(df.columns, pd.MultiIndex):
        # Decide which level is ticker: prefer the level that contains provided tickers.
        lvl0_values = set(map(str, df.columns.get_level_values(0)))
        lvl1_values = set(map(str, df.columns.get_level_values(1)))
        set_tickers = set(tickers)

        if set_tickers & lvl0_values:
            # Columns are (Ticker, Field) → we want to stack the Ticker level
            cols = df.copy()
            # After stack(level=0), index becomes [Date, <ticker-level-name or None>]
            stacked = cols.stack(level=0, future_stack=True)
        elif set_tickers & lvl1_values:
            # Columns are (Field, Ticker) → swap to (Ticker, Field) then stack
            cols = df.swaplevel(0, 1, axis=1)
            stacked = cols.stack(level=0, future_stack=True)
        else:
            # Fallback: assume common yfinance shape (Field, Ticker)
            cols = df.swaplevel(0, 1, axis=1)
            stacked = cols.stack(level=0, future_stack=True)

        # Normalize index to columns
        stacked = stacked.reset_index()

        # Find/normalize date and ticker column names
        # Date column is usually 'Date' after reset_index
        if "Date" in stacked.columns:
            stacked.rename(columns={"Date": "date"}, inplace=True)
        elif "date" not in stacked.columns:
            raise ValueError("Could not locate date column after stacking.")

        # Ticker column may be named with the original column level name or 'level_1'
        ticker_col = None
        for cand in ["ticker", "Ticker", "level_1", "Symbols", "symbol"]:
            if cand in stacked.columns:
                ticker_col = cand
                break
        if not ticker_col:
            # As a last resort, the last index column after reset_index is usually the ticker
            # Find all original index columns by difference
            # We expect price fields present; the remaining non-price, non-date column is ticker
            possible = [
                c for c in stacked.columns if c not in ["date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
            ]
            if possible:
                ticker_col = possible[0]

        if not ticker_col:
            raise ValueError("Could not locate ticker column after stacking.")

        stacked.rename(columns={ticker_col: "ticker"}, inplace=True)

        # Ensure expected price columns exist
        for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
            if col not in stacked.columns:
                stacked[col] = pd.NA

        stacked["date"] = pd.to_datetime(stacked["date"]).dt.strftime("%Y-%m-%d")
        stacked["ticker"] = stacked["ticker"].astype(str).str.upper()
        return stacked[["date", "ticker", "Open", "High", "Low", "Close", "Adj Close", "Volume"]]

    # SINGLE-TICKER CASE
    single = df.reset_index()
    if "Date" in single.columns:
        single.rename(columns={"Date": "date"}, inplace=True)
    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if col not in single.columns:
            single[col] = pd.NA
    ticker = tickers[0] if tickers else "TICKER"
    single["ticker"] = ticker.upper()
    single["date"] = pd.to_datetime(single["date"]).dt.strftime("%Y-%m-%d")
    return single[["date", "ticker", "Open", "High", "Low", "Close", "Adj Close", "Volume"]]


def _to_ndjson(df: pd.DataFrame) -> str:
    lines = []
    for _, row in df.iterrows():
        date_str = row["date"]
        ticker = row["ticker"]
        doc_id = f"{ticker}_{date_str}"

        doc = {
            "ticker": ticker,
            "date": date_str,
            "open": _safe_round(row.get("Open")),
            "high": _safe_round(row.get("High")),
            "low": _safe_round(row.get("Low")),
            "close": _safe_round(row.get("Close")),
            "adj_close": _safe_round(row.get("Adj Close")),
            "volume": _safe_int(row.get("Volume")),
        }

        lines.append(json.dumps({"index": {"_id": doc_id}}))
        lines.append(json.dumps(doc))
    return "\n".join(lines) + ("\n" if lines else "")


def fetch_prices(
    tickers: Union[str, Iterable[str]],
    start_date: str,
    end_date: str,
    output_file: str = DEFAULT_OUTPUT_FILE,
) -> str:
    tickers_list = _as_list(tickers)
    if not tickers_list:
        raise ValueError("No tickers provided.")

    # Validate dates
    _ = datetime.strptime(start_date, "%Y-%m-%d")
    _ = datetime.strptime(end_date, "%Y-%m-%d")

    df = _download_prices(tickers_list, start_date, end_date)
    ndjson = _to_ndjson(df)

    with open(output_file, "w") as f:
        f.write(ndjson)

    print(f"Done. Wrote {df.shape[0]} records to {output_file}")
    return output_file


def parse_args():
    p = argparse.ArgumentParser(description="Fetch daily OHLCV prices from yfinance and write NDJSON.")
    p.add_argument("tickers", help="Comma-separated tickers, e.g. AAPL,MSFT,TSLA")
    p.add_argument("start_date", help="Inclusive start date, YYYY-MM-DD")
    p.add_argument("end_date", help="Inclusive end date, YYYY-MM-DD")
    p.add_argument(
        "-o", "--output", default=DEFAULT_OUTPUT_FILE, help=f"Output NDJSON file (default: {DEFAULT_OUTPUT_FILE})"
    )
    return p.parse_args()


def main():
    args = parse_args()
    fetch_prices(args.tickers, args.start_date, args.end_date, args.output)


if __name__ == "__main__":
    main()
