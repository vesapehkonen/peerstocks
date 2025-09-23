import React, { useEffect, useState } from "react";
import axios from "axios";
import { Sparklines, SparklinesLine } from "react-sparklines";
import { Link, useNavigate } from "react-router-dom";
import api from "./api";

const stockTypes = ["Growth", "Value", "Dividend"];
const sectors = [
  "Technology",
  "Healthcare",
  "Finance",
  "Energy",
  "Utilities",
  "Consumer",
  "Industrial",
];

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

  // NEW: selection + compare
  const navigate = useNavigate();
  const [selected, setSelected] = useState(new Set());
  const MAX_COMPARE = 8;

  // Keep selection pruned to current result set
  useEffect(() => {
    if (!results?.length) { setSelected(new Set()); return; }
    const tickers = new Set(results.map(r => r.ticker));
    setSelected(prev => {
      const next = new Set();
      for (const t of prev) if (tickers.has(t)) next.add(t);
      return next;
    });
  }, [results]);

  const toggle = (ticker) => {
    setSelected(prev => {
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
        return sortConfig.direction === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      return sortConfig.direction === "asc" ? aVal - bVal : bVal - aVal;
    });
  }

  const allVisibleSelected =
    results.length > 0 && results.every(r => selected.has(r.ticker));

  return (
    <div className="max-w-5xl mx-auto bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 pt-4 md:pt-6 pb-8 px-4">
      <h1 className="text-xl md:text-2xl font-semibold tracking-tight leading-tight mb-4 text-gray-800 dark:text-gray-100 text-center">
        <span className="mr-2 text-lg md:text-xl align-middle" aria-hidden>🔎</span>
        Advanced Stock Search
      </h1>
      <form
        onSubmit={handleSubmit}
        className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow w-full space-y-6"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Left Column: Valuation + Growth */}
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-2">Valuation</h2>
              <div className="space-y-3">
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
              </div>
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2">Growth</h2>
              <div className="space-y-3">
                {["1y", "3y", "5y"].map((label, i) => {
                  const value = [revenueGrowth1y, revenueGrowth3y, revenueGrowth5y][i];
                  const setValue = [setRevenueGrowth1y, setRevenueGrowth3y, setRevenueGrowth5y][i];
                  return (
                    <label key={label} className="flex justify-between items-center">
                      <span className="text-sm font-medium">Revenue Growth ({label})</span>
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
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
            <div>
              <h2 className="text-lg font-semibold mb-2">Stock Types</h2>
              <fieldset disabled className="opacity-50"> {/*  when this feature is implemented remove this */}
              <div className="flex flex-col gap-2">
                {stockTypes.map((type) => (
                  <label key={type} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      value={type}
                      checked={selectedTypes.includes(type)}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setSelectedTypes((prev) =>
                          checked ? [...prev, type] : prev.filter((t) => t !== type)
                        );
                      }}
                    />
                    <span>{type}</span>
                  </label>
                ))}
              </div>
              </fieldset> {/*  when this feature is implemented remove this */}
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2">Sectors</h2>
              <div className="opacity-70"> {/*  when this feature is implemented remove this */}
              <select
                multiple
                value={selectedSectors}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions).map(
                    (opt) => opt.value
                  );
                  setSelectedSectors(selected);
                }}
                className="w-full p-2 text-sm border rounded dark:bg-gray-700 dark:text-white h-32"
                disabled /*  when this feature is implemented remove this line */
              >
                {sectors.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 mt-1">
                Hold Ctrl (or Cmd) to select multiple.
              </p>
              </div> {/*  when this feature is implemented remove this */}

            </div>
          </div>
        </div>

        <div className="text-center pt-4">
          <button
            type="submit"
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg"
          >
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
                Selected: {selected.size}{selected.size >= MAX_COMPARE ? ` / ${MAX_COMPARE}` : ""}
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
                      onChange={(e) => e.target.checked ? selectAllVisible() : clearSelection()}
                      checked={allVisibleSelected && selected.size > 0}
                      aria-label="Select all visible"
                    />
                  </th>
                  {[
                    ["Ticker", "ticker"],
                    ["P/E", "ttm_pe_ratio"],
                    ["Revenue Growth (1y)", "revenue_growth_1y"],
                    ["Revenue Growth (3y)", "revenue_growth_3y"],
                    ["Revenue Growth (5y)", "revenue_growth_5y"],
                    ["Price Growth (5y)", "price_growth_5y"],
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
                    <tr
                      key={row.ticker}
                      className="border-t hover:bg-gray-50 dark:hover:bg-gray-700"
                    >
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
                      <td className="p-2">{row.revenue_growth_3y != null ? row.revenue_growth_3y.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.revenue_growth_5y != null ? row.revenue_growth_5y.toFixed(2) : "–"}%</td>
                      <td className="p-2">{row.price_growth_5y != null ? row.price_growth_5y.toFixed(2) : "–"}%</td>
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
                          <Sparklines data={row.revenue_history.map(e => e.revenue)} width={80} height={20}>
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
