import requests
from datetime import datetime, timedelta
from opensearch_client import run_opensearch_query, get_opensearch_client

http_client = get_opensearch_client()


def fetch_earnings(ticker: str):
  query = {
      "size": 1000,
      "query": {
          "bool": {
              "must": [{
                  "term": {
                      "ticker": ticker
                  }
              }]
          }
      },
      "sort": [{
          "end_date": "asc"
      }]
  }
  data = run_opensearch_query(http_client, 'earnings_data', query)
  return data


def find_existing_trading_day(ticker, date_str):
  """Search back up to 7 days to find a matching trading day in stock_prices."""
  d = datetime.strptime(date_str, "%Y-%m-%d")
  for _ in range(7):
    check_date = d.strftime("%Y-%m-%d")
    query = {
        "query": {
            "bool": {
                "must": [{
                    "term": {
                        "ticker": ticker
                    }
                }, {
                    "term": {
                        "date": check_date
                    }
                }]
            }
        },
        "size": 1
    }
    hits = run_opensearch_query(http_client, 'stock_prices', query)
    if hits:
      return hits[0]["_source"]["close"]
    d -= timedelta(days=1)
  return None
