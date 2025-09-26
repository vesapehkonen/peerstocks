// src/TrendingTickers.jsx
import React from "react";
import { Link } from "react-router-dom";

const DEFAULT_TRENDING = ["AAPL", "TSLA", "MSFT", "GOOG", "AMZN"];

export default function TrendingTickers({ tickers = DEFAULT_TRENDING, onSelect }) {
  return (
    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-100">Trending</h3>
        <span className="text-xs text-gray-500">Quick picks</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => onSelect?.(t)}
            className="px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700
                       text-sm font-medium bg-gray-50 dark:bg-gray-900 hover:bg-gray-100
                       dark:hover:bg-gray-700 transition"
            aria-label={`Search ${t}`}
            title={`Search ${t}`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Optional: deep links to details/compare without extra clicks */}
      <div className="mt-3 text-sm text-blue-600 dark:text-blue-400 flex flex-wrap gap-3">
        {tickers.map((t) => (
          <Link key={`${t}-link`} to={`/stock/${t}`} className="underline hover:no-underline">
            {t} details →
          </Link>
        ))}
      </div>
    </div>
  );
}
