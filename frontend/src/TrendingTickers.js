// src/TrendingTickers.jsx
import React from "react";
import { Link } from "react-router-dom";

const DEFAULT_TRENDING = ["AAPL", "TSLA", "MSFT", "GOOG", "AMZN"];

export default function TrendingTickers({ tickers = DEFAULT_TRENDING, onSelect }) {
  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-300 mb-3">Explore</h3>

      {/* Trending tickers */}
      <div className="flex flex-wrap gap-2 mb-3">
        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => onSelect?.(t)}
            className="px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700
                   text-sm font-medium bg-gray-50 dark:bg-gray-900
                   hover:bg-gray-100 dark:hover:bg-gray-700 transition"
          >
            {t}
          </button>
        ))}
      </div>

      {/* Popular comparisons */}
      <div className="flex flex-wrap gap-2">
        <Link
          to="/compare?tickers=AAPL,MSFT&range=5Y"
          className="px-3 py-1.5 rounded-full border border-blue-400
           text-sm font-medium bg-blue-50
           hover:bg-blue-100 transition"
        >
          AAPL vs MSFT
        </Link>

        <Link
          className="px-3 py-1.5 rounded-full border border-blue-400
           text-sm font-medium bg-blue-50
           hover:bg-blue-100 transition"
        >
          NVDA vs AMD
        </Link>
      </div>
    </div>
  );
}
