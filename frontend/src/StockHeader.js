// StockHeader.js

import React, { useMemo, useState } from "react";

function formatNumber(num) {
  if (num == null) return null;
  if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + " billion";
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + " million";
  if (num >= 1_000) return (num / 1_000).toFixed(1) + " thousand";
  return num.toString();
}

function StatInline({ label, value }) {
  return (
    <div className="flex items-baseline gap-1 text-sm">
      <span className="text-gray-500">{label}:</span>
      <span className="font-medium">{value ?? "—"}</span>
    </div>
  );
}

export default function StockHeader({ ticker, metadata, dailyPrices }) {
  const [showDesc, setShowDesc] = useState(false);

  const snapshot = useMemo(() => {
    if (!Array.isArray(dailyPrices) || dailyPrices.length === 0) return {};
    const last = dailyPrices[dailyPrices.length - 1];
    const prev = dailyPrices.length > 1 ? dailyPrices[dailyPrices.length - 2] : null;

    const change = prev ? (last.price ?? 0) - (prev.price ?? 0) : null;
    const changePct = prev && prev.price ? (change / prev.price) * 100 : null;

    return {
      lastPrice: last.price ?? null,
      lastDate: last.date ?? null,
      change,
      changePct,
    };
  }, [dailyPrices]);

  const up = (snapshot.change ?? 0) > 0;
  const down = (snapshot.change ?? 0) < 0;
  const currency = metadata?.currency_name?.toUpperCase?.();

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4 shadow space-y-3">
      {/* Row 1: identity + price */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Identity */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-gray-100 dark:bg-gray-800 grid place-items-center text-xs font-bold">
            {ticker?.slice(0, 4)}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-semibold">{metadata?.name || ticker}</h2>
              <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-800">{ticker}</span>
              {metadata?.primary_exchange && (
                <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-800">
                  {metadata.primary_exchange}
                </span>
              )}
              {currency && (
                <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-800">{currency}</span>
              )}
            </div>
            <div className="text-xs text-gray-500 flex items-center gap-2 mt-1 flex-wrap">
              {metadata?.sector && <span>{metadata.sector}</span>}
              {metadata?.sic_description && <span>{metadata.sic_description}</span>}
              {metadata?.homepage_url && (
                <a
                  href={metadata.homepage_url}
                  className="underline decoration-dotted"
                  target="_blank"
                  rel="noreferrer"
                >
                  Website
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Price snapshot */}
        <div className="text-right">
          <div className="text-2xl font-bold">
            {snapshot.lastPrice != null ? snapshot.lastPrice.toLocaleString() : "—"} {currency}
          </div>
          <div
            className={`text-sm ${
              up ? "text-green-600" : down ? "text-red-600" : "text-gray-500"
            }`}
          >
            {snapshot.change != null && snapshot.changePct != null
              ? `${snapshot.change > 0 ? "▲" : snapshot.change < 0 ? "▼" : ""} ${snapshot.change.toFixed(
                  2
                )} (${snapshot.changePct.toFixed(2)}%)`
              : "—"}
          </div>
          {snapshot.lastDate && (
            <div className="text-xs text-gray-500">
              {new Date(snapshot.lastDate).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>

      {/* Row 2: inline KPIs */}
      <div className="flex flex-wrap gap-6 text-sm">
        <StatInline
          label="Shares Outstanding"
          value={formatNumber(metadata?.share_class_shares_outstanding)}
        />
        {/* Optional: Market Cap if you want */}
        {snapshot.lastPrice != null && metadata?.share_class_shares_outstanding && (
          <StatInline
            label="Market Cap"
            value={formatNumber(snapshot.lastPrice * metadata.share_class_shares_outstanding)}
          />
        )}
      </div>

     {/* Optional company description (collapsible) */}
      {metadata?.description && (
        <div className="mt-4">
          <button
            className="text-sm underline decoration-dotted"
            onClick={() => setShowDesc((s) => !s)}
          >
            {showDesc ? "Hide description" : "Show description"}
          </button>
          {showDesc && (
            <p className="mt-2 text-sm text-gray-700 dark:text-gray-200">
              {metadata.description}
            </p>
          )}
        </div>
      )}    

    </div>
  );
}
