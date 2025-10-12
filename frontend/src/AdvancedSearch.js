import React, { useEffect, useState } from "react";
import axios from "axios";
import { Sparklines, SparklinesLine } from "react-sparklines";
import { Link, useNavigate } from "react-router-dom";
import api from "./api";

const stockTypes = ["Growth", "Value", "Dividend"];
const sectors = ["Technology", "Healthcare", "Finance", "Energy", "Utilities", "Consumer", "Industrial"];

function AdvancedSearch() {
  const [peMax, setPeMax] = useState("");
  const [priceGrowth, setPriceGrowth] = useState("");
  const [revenueGrowth5y, setRevenueGrowth5y] = useState("");
  const [revenueGrowth3y, setRevenueGrowth3y] = useState("");
  const [revenueGrowth1y, setRevenueGrowth1y] = useState("");
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [selectedSectors, setSelectedSectors] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sortConfig, setSortConfig] = useState({ key: "ticker", direction: "asc" });
  const [debtToEquityMax, setDebtToEquityMax] = useState("");
  const [marketCapBucket, setMarketCapBucket] = useState(""); // Any/<2B/2-10B/10-100B/>100B
  const [roaMin, setRoaMin] = useState("");
  const [roeMin, setRoeMin] = useState("");
  const [dividendYieldMin, setDividendYieldMin] = useState(""); // disabled UI, placeholder only

  // NEW: selection + compare
  const navigate = useNavigate();
  const [selected, setSelected] = useState(new Set());
  const MAX_COMPARE = 8;

  // Keep selection pruned to current result set
  useEffect(() => {
    if (!results?.length) {
      setSelected(new Set());
      return;
    }
    const tickers = new Set(results.map((r) => r.ticker));
    setSelected((prev) => {
      const next = new Set();
      for (const t of prev) if (tickers.has(t)) next.add(t);
      return next;
    });
  }, [results]);

  const toggle = (ticker) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        if (next.size >= MAX_COMPARE) return next; // cap
        next.add(ticker);
      }
      return next;
    });
  };

  const selectAllVisible = () => {
    const next = new Set(selected);
    for (const r of results) {
      if (next.size >= MAX_COMPARE) break;
      next.add(r.ticker);
    }
    setSelected(next);
  };

  const clearSelection = () => setSelected(new Set());

  const goCompare = () => {
    if (!selected.size) return;
    const tickers = [...selected].join(",");
    navigate({ pathname: "/compare", search: `?tickers=${tickers}` });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const searchParams = {
      peMax: peMax ? parseFloat(peMax) : null,
      priceGrowth: priceGrowth ? parseFloat(priceGrowth) : null,
      revenueGrowth1y: revenueGrowth1y ? parseFloat(revenueGrowth1y) : null,
      revenueGrowth3y: revenueGrowth3y ? parseFloat(revenueGrowth3y) : null,
      revenueGrowth5y: revenueGrowth5y ? parseFloat(revenueGrowth5y) : null,
      debtToEquityMax: debtToEquityMax ? parseFloat(debtToEquityMax) : null,
      marketCapBucket: marketCapBucket || null, // "", "<2B", "2-10B", "10-100B", ">100B"
      roaMin: roaMin ? parseFloat(roaMin) : null,
      roeMin: roeMin ? parseFloat(roeMin) : null,
      dividendYieldMin: null, // UI disabled; backend not supported yet
      stockType: selectedTypes,
      sector: selectedSectors,
    };

    setLoading(true);
    try {
      const response = await api.post("/advanced-search", searchParams);
      setResults(response.data || []);
    } catch (err) {
      console.error("Error fetching search results:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === "asc" ? "desc" : "asc" };
      } else {
        return { key, direction: "asc" };
      }
    });
  };

  const sortedResults = [...results];
  if (sortConfig.key) {
    sortedResults.sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === "string") {
        return sortConfig.direction === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortConfig.direction === "asc" ? aVal - bVal : bVal - aVal;
    });
  }

  const formatMarketCap = (n) => {
    if (n == null) return "–";
    const abs = Math.abs(n);
    if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (abs >= 1e9)  return `$${(n / 1e9).toFixed(2)}B`;
    if (abs >= 1e6)  return `$${(n / 1e6).toFixed(2)}M`;
    return `$${n.toFixed(0)}`;
  };
  
  const allVisibleSelected = results.length > 0 && results.every((r) => selected.has(r.ticker));

  return (
    <div className="max-w-5xl mx-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 pt-4 md:pt-6 pb-8 px-4">
      <h1 className="text-xl md:text-2xl font-semibold tracking-tight leading-tight mb-4 text-gray-800 dark:text-gray-100 text-center">
        <span className="mr-2 text-lg md:text-xl align-middle" aria-hidden>
          🔎
        </span>
        Advanced Stock Search
      </h1>
      <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow w-full space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column: Valuation + Growth */}
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-2">Valuation</h2>
              <div className="space-y-2">
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Max P/E Ratio</span>
                  <input
                    type="number"
                    value={peMax}
                    onChange={(e) => setPeMax(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="15"
                  />
                </label>
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Max Debt-to-Equity</span>
                  <input
                    type="number"
                    value={debtToEquityMax}
                    onChange={(e) => setDebtToEquityMax(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="1.5"
                    step="0.01"
                  />
                </label>
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Market Cap</span>
                  <select
                    value={marketCapBucket}
                    onChange={(e) => setMarketCapBucket(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                  >
                    <option value="">Any</option>
                    <option value="<2B">&lt; $2B</option>
                    <option value="2-10B">$2B–$10B</option>
                    <option value="10-100B">$10B–$100B</option>
                    <option value=">100B">&gt; $100B</option>
                  </select>
                </label>
              </div>
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2">Growth</h2>
              <div className="space-y-2">
                {[
                  { label: "1y", value: revenueGrowth1y, set: setRevenueGrowth1y },
                  { label: "5y", value: revenueGrowth5y, set: setRevenueGrowth5y },
                ].map(({ label, value, set }) => {
                  return (
                    <label key={label} className="flex justify-between items-center">
                      <span className="text-sm font-medium">Revenue Growth ({label})</span>
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => set(e.target.value)}
                        className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                        placeholder="5"
                      />
                    </label>
                  );
                })}
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Price Growth (5y)</span>
                  <input
                    type="number"
                    value={priceGrowth}
                    onChange={(e) => setPriceGrowth(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="8"
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Right Column: Types + Sectors */}
          <div className="space-y-6">
            {/*<div>
               <h2 className="text-lg font-semibold mb-2">Stock Types</h2>
               <fieldset disabled className="opacity-50">

                 ...
               </fieldset>
            </div>*/}

            <div>
              <h2 className="text-lg font-semibold mb-2">Profitability</h2>
              <div className="space-y-2">
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Min ROA (%)</span>
                  <input
                    type="number"
                    value={roaMin}
                    onChange={(e) => setRoaMin(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="5"
                    step="0.1"
                  />
                </label>
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Min ROE (%)</span>
                  <input
                    type="number"
                    value={roeMin}
                    onChange={(e) => setRoeMin(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="10"
                    step="0.1"
                  />
                </label>
              </div>
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2">Dividends</h2>
              <fieldset disabled title="Disabled: dividends data not available yet" className="opacity-50">
                <label className="flex justify-between items-center">
                  <span className="text-sm font-medium">Min Dividend Yield (%)</span>
                  <input
                    type="number"
                    value={dividendYieldMin}
                    onChange={(e) => setDividendYieldMin(e.target.value)}
                    className="w-24 p-1.5 text-sm border rounded dark:bg-gray-700 dark:text-white"
                    placeholder="2"
                  />
                </label>
              </fieldset>
            </div>
            <div>
              <h2 className="text-lg font-semibold mb-2">Sectors</h2>

                <select
                  multiple
                  value={selectedSectors}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                    setSelectedSectors(selected);
                  }}
                  className="w-full p-2 text-sm border rounded dark:bg-gray-700 dark:text-white h-32"

                >
                  {sectors.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <p className="text-sm text-gray-500 mt-1">Hold Ctrl (or Cmd) to select multiple.</p>


            </div>
          </div>
        </div>

        <div className="text-center pt-4">
          <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg">
            Search
          </button>
        </div>
      </form>

      {loading && <p className="mt-6 text-center text-blue-600">Searching...</p>}

      {results.length > 0 && (
        <div className="mt-6 bg-white dark:bg-gray-800 p-4 rounded-1g shadow">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold">Search Results</h2>
            <div className="ml-auto flex items-center gap-2">
              <button
                className="rounded-md border px-3 py-1 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                onClick={selectAllVisible}
                disabled={!results.length || selected.size >= MAX_COMPARE}
                title={`Select up to ${MAX_COMPARE}`}
              >
                Select visible
              </button>
              <button
                className="rounded-md border px-3 py-1 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                onClick={clearSelection}
                disabled={!selected.size}
              >
                Clear
              </button>
              <span className="text-sm text-gray-600 dark:text-gray-300">
                Selected: {selected.size}
                {selected.size >= MAX_COMPARE ? ` / ${MAX_COMPARE}` : ""}
              </span>
              <button
                className={`rounded-md px-3 py-1 text-sm ${
                  selected.size
                    ? "bg-black text-white dark:bg-white dark:text-black"
                    : "border text-gray-400 cursor-not-allowed"
                }`}
                onClick={goCompare}
                disabled={!selected.size}
              >
                Compare ({selected.size})
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm table-auto">
              <thead>
                <tr className="border-b">
                  <th className="p-2">
                    {/* header checkbox: select all (visible) */}
                    <input
                      type="checkbox"
                      onChange={(e) => (e.target.checked ? selectAllVisible() : clearSelection())}
                      checked={allVisibleSelected && selected.size > 0}
                      aria-label="Select all visible"
                    />
                  </th>
                  {[
                    ["Ticker", "ticker"],
                    ["P/E", "ttm_pe_ratio"],
                    ["Revenue Growth (1y)", "revenue_growth_1y"],
                    ["Revenue Growth (5y)", "revenue_growth_5y"],
                    ["Price Growth (5y)", "price_growth_5y"],
                    ["ROA (%)", "roa"],
                    ["ROE (%)", "roe"],
                    ["D/E", "debt_to_equity"],
                    ["Market Cap", "market_cap"],
                    ["Div Yield (%)", "dividend_yield"],
                  ].map(([label, key]) => (

                    <th
                      key={key}
                      className="text-left p-2 cursor-pointer select-none align-top"
                      onClick={() => handleSort(key)}
                    >
                      <span className="inline-block whitespace-normal">
                        {label}
                        {sortConfig.key === key && (
                          <span className="ml-1 text-xs align-middle">
                            {sortConfig.direction === "asc" ? "▲" : "▼"}
                          </span>
                        )}
                      </span>
                    </th>
                  ))}
                  <th className="text-left p-2">Price Trend</th>
                  <th className="text-left p-2">Revenue Trend</th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((row) => {
                  const isChecked = selected.has(row.ticker);
                  const disableCheckbox = !isChecked && selected.size >= MAX_COMPARE;
                  return (
                    <tr key={row.ticker} className="border-t hover:bg-gray-50 dark:hover:bg-gray-700">
                      <td className="p-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggle(row.ticker)}
                          disabled={disableCheckbox}
                          aria-label={`Select ${row.ticker}`}
                          title={disableCheckbox ? `Max ${MAX_COMPARE} tickers` : ""}
                        />
                      </td>
                      <td className="p-2">
                        <Link to={`/stock/${row.ticker}`} className="text-blue-600 hover:underline">
                          {row.ticker}
                        </Link>
                      </td>
                      <td className="p-2">{row.ttm_pe_ratio ?? "–"}</td>
                      <td className="p-2">{row.revenue_growth_1y != null ? row.revenue_growth_1y.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.revenue_growth_5y != null ? row.revenue_growth_5y.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.price_growth_5y != null ? row.price_growth_5y.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.roa != null ? row.roa.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.roe != null ? row.roe.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.debt_to_equity != null ? row.debt_to_equity.toFixed(2) : "–"}</td>
                      <td className="p-2">{formatMarketCap(row.market_cap)}</td>
                      <td className="p-2">{row.dividend_yield != null ? row.dividend_yield.toFixed(2) : "–"}%</td>
                      <td className="p-2">
                        {row.price_history ? (
                          <Sparklines data={row.price_history} width={80} height={20}>
                            <SparklinesLine color="blue" />
                          </Sparklines>
                        ) : (
                          "–"
                        )}
                      </td>
                      <td className="p-2">
                        {row.revenue_history && row.revenue_history.length > 0 ? (
                          <Sparklines data={row.revenue_history.map((e) => e.revenue)} width={80} height={20}>
                            <SparklinesLine />
                          </Sparklines>
                        ) : (
                          "–"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdvancedSearch;
